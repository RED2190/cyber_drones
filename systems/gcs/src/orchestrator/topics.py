"""Топики и actions для OrchestratorComponent."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    ORCHESTRATOR = f"{_P}components.orchestrator"
    PATH_PLANNER = f"{_P}components.path_planner"
    MISSION_CONVERTER = f"{_P}components.mission_converter"
    DRONE_MANAGER = f"{_P}components.drone_manager"
    DRONE_STORE = f"{_P}components.drone_store"
    MISSION_STORE = f"{_P}components.mission_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.ORCHESTRATOR,
            cls.PATH_PLANNER,
            cls.MISSION_CONVERTER,
            cls.DRONE_MANAGER,
            cls.DRONE_STORE,
            cls.MISSION_STORE,
        ]


class OrchestratorActions:
    TASK_SUBMIT = "task.submit"
    TASK_ASSIGN = "task.assign"
    TASK_START = "task.start"
