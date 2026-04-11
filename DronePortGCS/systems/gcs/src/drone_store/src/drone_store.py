from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from broker.src.system_bus import SystemBus
from sdk.base_redis_store_component import BaseRedisStoreComponent
from systems.gcs.src.drone_store.topics import ComponentTopics, DroneStoreActions

logger = logging.getLogger(__name__)


class DroneStoreComponent(BaseRedisStoreComponent):
    def __init__(self, component_id: str, bus: SystemBus):
        self.initial_fleet: Dict[str, Dict[str, Any]] = {}
        super().__init__(
            component_id=component_id,
            component_type="gcs_drone_store",
            topic=ComponentTopics.GCS_DRONE_STORE,
            bus=bus,
            redis_db_env="DRONE_STORE_REDIS_DB",
            redis_default_db=1,
        )

    def _drone_key(self, drone_id: str) -> str:
        return f"gcs:drone:{drone_id}"

    def _all_drones_key(self) -> str:
        return "gcs:drones:all"

    def _available_drones_key(self) -> str:
        return "gcs:drones:available"

    def _read_drone(self, drone_id: str) -> Optional[Dict[str, Any]]:
        raw = self.redis_client.get(self._drone_key(drone_id))
        if raw is None:
            return None
        return json.loads(raw)

    def _write_drone(self, drone_id: str, state: Dict[str, Any]) -> None:
        self.redis_client.set(self._drone_key(drone_id), json.dumps(state, ensure_ascii=False))
        self.redis_client.sadd(self._all_drones_key(), drone_id)
        if state.get("status") == "available":
            self.redis_client.sadd(self._available_drones_key(), drone_id)
        else:
            self.redis_client.srem(self._available_drones_key(), drone_id)

    def _all_drone_ids(self) -> Set[str]:
        return set(self.redis_client.smembers(self._all_drones_key()))

    def _available_drone_ids(self) -> Set[str]:
        return set(self.redis_client.smembers(self._available_drones_key()))

    def _update_drone_from_telemetry(self, drone_id: str, telemetry: Dict[str, Any], allow_register: bool = True) -> None:
        drone_state = self._read_drone(drone_id)

        if drone_state is None:
            drone_state = {}
            now = datetime.now(timezone.utc).isoformat()

            drone_state.setdefault("connected_at", now)
            drone_state["status"] = "connected"

        if "battery" in telemetry:
            drone_state["battery"] = int(telemetry.get("battery", 0))

        latitude = telemetry.get("latitude")
        longitude = telemetry.get("longitude")
        altitude = telemetry.get("altitude")
        if latitude is not None and longitude is not None:
            drone_state["last_position"] = {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
            }

        self._write_drone(drone_id, drone_state)
        return None


    def _register_handlers(self):
        self.register_handler(DroneStoreActions.GET_DRONE, self._handle_get_drone)
        self.register_handler(DroneStoreActions.UPDATE_DRONE, self._handle_update_drone)
        self.register_handler(DroneStoreActions.SAVE_TELEMETRY, self._handle_save_telemetry)

    def _handle_get_drone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        drone_id = message.get("payload", {}).get("drone_id")
        logger.info("[%s] get_drone drone_id=%s", self.component_id, drone_id)
        return {
            "from": self.component_id,
            "drone": self._read_drone(drone_id),
        }


    def _handle_save_telemetry(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload")
        telemetry = payload.get("telemetry")
        drone_id = telemetry.get("drone_id")
        logger.info("[%s] save_telemetry drone_id=%s telemetry=%r", self.component_id, drone_id, telemetry)

        return self._update_drone_from_telemetry(drone_id, telemetry)

    def _handle_update_drone(self, message: Dict[str, Any]) -> None:
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")
        status = payload.get("status")
        logger.info("[%s] update_drone drone_id=%s status=%s", self.component_id, drone_id, status)

        drone_state = self._read_drone(drone_id) or {}
        drone_state["status"] = status

        self._write_drone(drone_id, drone_state)

        return None
