"""PathPlanner с заглушкой построения маршрута."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict

from broker.src.system_bus import SystemBus
from sdk.base_component import BaseComponent
from sdk.wpl_generator import expand_two_points_to_path
from sdk.wpl_generator_2 import expand_three_points_to_snake_path
from systems.gcs.src.contracts import MissionStatus
from systems.gcs.src.path_planner.topics import ComponentTopics, PathPlannerActions

logger = logging.getLogger(__name__)


class PathPlannerComponent(BaseComponent):
    def __init__(self, component_id: str, bus: SystemBus):
        super().__init__(
            component_id=component_id,
            component_type="gcs_path_planner",
            topic=ComponentTopics.GCS_PATH_PLANNER,
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler(PathPlannerActions.PATH_PLAN, self._handle_path_plan)

    @staticmethod
    def _build_route(waypoints: list[Dict[str, Any]]) -> list[Dict[str, float]]:
        try:
            seed_points = [
                {
                    "lat": float(point["lat"]),
                    "lon": float(point["lon"]),
                    "alt_m": float(point.get("alt_m", 0.0)),
                }
                for point in waypoints
            ]
        except (KeyError, TypeError, ValueError):
            raise ValueError("Waypoints must be a list of points with lat/lon/alt_m")

        if len(seed_points) == 2:
            return expand_two_points_to_path(seed_points)

        if len(seed_points) == 3:
            return expand_three_points_to_snake_path(seed_points)

        raise ValueError("Task must contain either 2 or 3 route points")

    def _handle_path_plan(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        mission_id = payload.get("mission_id")
        task = payload.get("task", {})
        correlation_id = message.get("correlation_id")
        logger.info("[%s] path_plan mission_id=%s correlation_id=%s", self.component_id, mission_id, correlation_id)

        waypoints_input = task.get("waypoints")
        if not isinstance(waypoints_input, list):
            return {
                "from": self.component_id,
                "error": "failed to build route",
            }

        try:
            waypoints = self._build_route(waypoints_input)
        except ValueError:
            logger.warning("[%s] path_plan failed to build route mission_id=%s input=%r", self.component_id, mission_id, waypoints_input)
            return {
                "from": self.component_id,
                "error": "failed to build route",
            }

        now = datetime.now(timezone.utc).isoformat()

        publish_message = {
            "action": "store.save_mission",
            "sender": self.component_id,
            "payload": {
                "mission": {
                    "mission_id": mission_id,
                    "waypoints": waypoints,
                    "status": MissionStatus().CREATED,
                    "assigned_drone": None,
                    "created_at": now,
                    "updated_at": now,
                }
            },
        }
        if correlation_id:
            publish_message["correlation_id"] = correlation_id

        self.bus.publish(
            ComponentTopics.GCS_MISSION_STORE,
            publish_message,
        )
        logger.info("[%s] path_plan published mission_id=%s waypoints=%s", self.component_id, mission_id, len(waypoints))

        return {
            "from": self.component_id,
            "mission_id": mission_id,
            "waypoints": waypoints,
        }
