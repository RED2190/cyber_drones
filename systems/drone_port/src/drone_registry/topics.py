"""Топики и actions для DroneRegistry в составе drone_port."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    DRONE_REGISTRY = f"{_P}components.drone_registry"
    DRONE_MANAGER = f"{_P}components.drone_manager"
    CHARGING_MANAGER = f"{_P}components.charging_manager"

    @classmethod
    def all(cls) -> list:
        return [
            cls.DRONE_MANAGER,
            cls.DRONE_REGISTRY,
            cls.CHARGING_MANAGER,
        ]


class DroneRegistryActions:
    REGISTER_DRONE = "register_drone"
    GET_DRONE = "get_drone"
    GET_AVAILABLE_DRONES = "get_available_drones"
    DELETE_DRONE = "delete_drone"
    CHARGING_STARTED = "charging_started"
    UPDATE_BATTERY = "update_battery"
