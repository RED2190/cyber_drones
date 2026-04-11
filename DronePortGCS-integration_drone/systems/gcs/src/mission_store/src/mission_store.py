from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from broker.src.system_bus import SystemBus
from sdk.base_redis_store_component import BaseRedisStoreComponent
from systems.gcs.src.mission_store.topics import ComponentTopics, MissionStoreActions


class MissionStoreComponent(BaseRedisStoreComponent):
    def __init__(self, component_id: str, bus: SystemBus):
        super().__init__(
            component_id=component_id,
            component_type="gcs_mission_store",
            topic=ComponentTopics.GCS_MISSION_STORE,
            bus=bus,
            redis_db_env="MISSION_STORE_REDIS_DB",
            redis_default_db=0,
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

        self._write_mission(mission)

        return None

    def _handle_get_mission(self, message: Dict[str, Any]) -> Dict[str, Any]:
        mission_id = message.get("payload", {}).get("mission_id")
        mission = self._read_mission(mission_id)

        return {
            "from": self.component_id,
            "mission": mission, 
        }

    def _handle_update_mission(self, message: Dict[str, Any]) -> None:
        payload = message.get("payload")
        mission_id = payload.get("mission_id")
        fields = payload.get("fields")

        mission = self._read_mission(mission_id)

        mission.update(fields)
        mission["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._write_mission(mission)

        return None
