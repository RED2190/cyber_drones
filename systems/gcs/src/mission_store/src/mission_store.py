from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis
from broker.src.system_bus import SystemBus
from sdk.base_component import BaseComponent
from ..topics import ComponentTopics, MissionStoreActions

logger = logging.getLogger(__name__)


class MissionStoreComponent(BaseComponent):
    def __init__(self, component_id: str, bus: SystemBus):
        redis_host = os.environ.get("REDIS_HOST", "redis")
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        redis_db = int(os.environ.get("MISSION_STORE_REDIS_DB", "0"))

        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )

        try:
            self.redis_client.ping()
            logger.info(
                "[%s] Redis connected at %s:%s db=%s",
                component_id,
                redis_host,
                redis_port,
                redis_db,
            )
        except redis.ConnectionError as exc:
            logger.warning(
                "[%s] Redis not available at %s:%s db=%s - %s",
                component_id,
                redis_host,
                redis_port,
                redis_db,
                exc,
            )

        super().__init__(
            component_id=component_id,
            component_type="gcs_mission_store",
            topic=ComponentTopics.MISSION_STORE,
            bus=bus,
        )

    def _mission_key(self, mission_id: str) -> str:
        return f"gcs:mission:{mission_id}"

    def _read_json(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self.redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def _write_json(self, key: str, data: Dict[str, Any]) -> None:
        self.redis_client.set(key, json.dumps(data, ensure_ascii=False))

    def _read_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        return self._read_json(self._mission_key(mission_id))

    def _write_mission(self, mission: Dict[str, Any]) -> None:
        mission_id = mission["mission_id"]
        self._write_json(self._mission_key(mission_id), mission)

    def _register_handlers(self):
        self.register_handler(MissionStoreActions.SAVE_MISSION, self._handle_save_mission)
        self.register_handler(MissionStoreActions.GET_MISSION, self._handle_get_mission)
        self.register_handler(MissionStoreActions.UPDATE_MISSION, self._handle_update_mission)

    def _handle_save_mission(self, message: Dict[str, Any]) -> None:
        mission = message.get("payload", {}).get("mission", {})
        mission_id = mission.get("mission_id")
        logger.info("[%s] save_mission mission_id=%s mission=%r", self.component_id, mission_id, mission)

        self._write_mission(mission)

        return None

    def _handle_get_mission(self, message: Dict[str, Any]) -> Dict[str, Any]:
        mission_id = message.get("payload", {}).get("mission_id")
        mission = self._read_mission(mission_id)
        logger.info("[%s] get_mission mission_id=%s found=%s", self.component_id, mission_id, mission is not None)

        return {
            "from": self.component_id,
            "mission": mission, 
        }

    def _handle_update_mission(self, message: Dict[str, Any]) -> None:
        payload = message.get("payload") or {}
        mission_id = payload.get("mission_id")
        fields = payload.get("fields")
        logger.info("[%s] update_mission mission_id=%s fields=%r", self.component_id, mission_id, fields)

        if not mission_id:
            return

        mission = self._read_mission(mission_id)
        if mission is None:
            return

        # Отсутствие ключа fields даёт None - dict.update(None) вызывает TypeError
        mission.update(fields or {})
        mission["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._write_mission(mission)

        return None

