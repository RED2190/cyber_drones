"""Topics and actions for MissionStoreComponent."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    MISSION_STORE = f"{_P}components.mission_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.MISSION_STORE,
        ]


class MissionStoreActions:
    SAVE_MISSION = "store.save_mission"
    GET_MISSION = "store.get_mission"
    UPDATE_MISSION = "store.update_mission"
