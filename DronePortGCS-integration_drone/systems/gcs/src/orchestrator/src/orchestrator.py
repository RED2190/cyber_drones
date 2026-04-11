"""OrchestratorComponent"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from broker.src.system_bus import SystemBus
from sdk.base_component import BaseComponent
from systems.gcs.src.orchestrator.topics import OrchestratorActions, ComponentTopics
from systems.gcs.src.path_planner.topics import PathPlannerActions
from systems.gcs.src.mission_converter.topics import MissionActions
from systems.gcs.src.drone_manager.topics import DroneManagerActions


# Единая точка входа для команд эксплуатанта.
class OrchestratorComponent(BaseComponent):
    def __init__(self, component_id: str, bus: SystemBus):
        super().__init__(
            component_id=component_id,
            component_type="gcs_orchestrator",
            topic=ComponentTopics.GCS_ORCHESTRATOR,
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler(OrchestratorActions.TASK_SUBMIT, self._handle_task_submit)
        self.register_handler(OrchestratorActions.TASK_ASSIGN, self._handle_task_assign)
        self.register_handler(OrchestratorActions.TASK_START, self._handle_task_start)

    def _handle_task_submit(self, message: Dict[str, Any]) -> Dict[str, Any]:
        task_payload = message.get("payload", {})
        correlation_id = message.get("correlation_id")
        mission_id = f"m-{uuid4().hex[:12]}"

        planned_message = {
            "action": PathPlannerActions.PATH_PLAN,
            "sender": self.component_id,
            "payload": {
                "mission_id": mission_id,
                "task": task_payload
            },
        }
        if correlation_id:
            planned_message["correlation_id"] = correlation_id

        planned = self.bus.request(
            ComponentTopics.GCS_PATH_PLANNER,
            planned_message,
            timeout=10.0,
        )

        if planned and planned.get("success"):
            payload = planned.get("payload", {})
            waypoints = payload.get("waypoints", [])

            if isinstance(waypoints, list) and len(waypoints) >= 4:
                return {
                    "from": self.component_id,
                    "mission_id": mission_id,
                    "waypoints": waypoints,
                }

        return {
            "from": self.component_id, 
            "error": "failed to build route"
        }


    def _handle_task_assign(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        correlation_id = message.get("correlation_id")
        mission_id = payload.get("mission_id")
        drone_id = payload.get("drone_id")

        prepared_message = {
            "action": MissionActions.MISSION_PREPARE,
            "sender": self.component_id,
            "payload": {
                "mission_id": mission_id,
            },
        }
        if correlation_id:
            prepared_message["correlation_id"] = correlation_id

        prepared = self.bus.request(
            ComponentTopics.GCS_MISSION_CONVERTER,
            prepared_message,
            timeout=30.0,
        )

        if prepared and prepared.get("success"):
            prepared_payload = prepared.get("payload", {})
            prepared_mission = prepared_payload.get("mission", {})
            wpl = prepared_mission.get("wpl")

            if wpl:
                publish_message = {
                    "action": DroneManagerActions.MISSION_UPLOAD,
                    "sender": self.component_id,
                    "payload": {
                        "mission_id": mission_id,
                        "drone_id": drone_id,
                        "wpl": wpl,
                    },
                }
                if correlation_id:
                    publish_message["correlation_id"] = correlation_id

                self.bus.publish(
                    ComponentTopics.GCS_DRONE_MANAGER,
                    publish_message,
                )

        return None


    def _handle_task_start(self, message: Dict[str, Any]) -> None:
        payload = message.get("payload", {})
        correlation_id = message.get("correlation_id")
        mission_id = payload.get("mission_id")
        drone_id = payload.get("drone_id")

        publish_message = {
            "action": DroneManagerActions.MISSION_START,
            "sender": self.component_id,
            "payload": {
                "mission_id": mission_id,
                "drone_id": drone_id
            },
        }
        if correlation_id:
            publish_message["correlation_id"] = correlation_id

        self.bus.publish(
            ComponentTopics.GCS_DRONE_MANAGER,
            publish_message,
        )

        return None
