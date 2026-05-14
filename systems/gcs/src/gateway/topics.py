"""Топики и внешние actions для gateway GCS."""

import os

from ..orchestrator.topics import OrchestratorActions


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    GCS = f"{_P}systems.gcs"


class ComponentTopics:
    DRONE_MANAGER = f"{_P}components.drone_manager"
    DRONE_STORE = f"{_P}components.drone_store"
    MISSION_CONVERTER = f"{_P}components.mission_converter"
    MISSION_STORE = f"{_P}components.mission_store"
    ORCHESTRATOR = f"{_P}components.orchestrator"
    PATH_PLANNER = f"{_P}components.path_planner"

    @classmethod
    def all(cls) -> list:
        return [
            cls.DRONE_MANAGER,
            cls.DRONE_STORE,
            cls.MISSION_CONVERTER,
            cls.MISSION_STORE,
            cls.ORCHESTRATOR,
            cls.PATH_PLANNER,
        ]


class GatewayActions:
    TASK_SUBMIT = OrchestratorActions.TASK_SUBMIT
    TASK_ASSIGN = OrchestratorActions.TASK_ASSIGN
    TASK_START = OrchestratorActions.TASK_START
