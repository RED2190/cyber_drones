"""Топики и actions для PathPlannerComponent."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    PATH_PLANNER = f"{_P}components.path_planner"
    MISSION_STORE = f"{_P}components.mission_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.PATH_PLANNER,
            cls.MISSION_STORE,
        ]


class PathPlannerActions:
    PATH_PLAN = "path.plan"
