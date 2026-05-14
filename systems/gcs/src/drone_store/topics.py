"""Topics and actions for DroneStoreComponent."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    DRONE_STORE = f"{_P}components.drone_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.DRONE_STORE,
        ]


class DroneStoreActions:
    GET_DRONE = "store.get_drone"
    UPDATE_DRONE = "store.update_drone"
    SAVE_TELEMETRY = "telemetry.save"
