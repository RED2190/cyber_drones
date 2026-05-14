"""Топики и actions для DroneManagerComponent."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    DRONE_MANAGER = f"{_P}components.drone_manager"
    MISSION_STORE = f"{_P}components.mission_store"
    DRONE_STORE = f"{_P}components.drone_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.DRONE_MANAGER,
            cls.MISSION_STORE,
            cls.DRONE_STORE,
        ]


class DroneManagerActions:
    MISSION_UPLOAD = "mission.upload"
    MISSION_START = "mission.start"
