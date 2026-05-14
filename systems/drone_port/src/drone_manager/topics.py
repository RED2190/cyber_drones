"""Топики и actions для DroneManager в составе drone_port."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    DRONE_MANAGER = f"{_P}components.drone_manager"
    CHARGING_MANAGER = f"{_P}components.charging_manager"
    PORT_MANAGER = f"{_P}components.port_manager"
    DRONE_REGISTRY = f"{_P}components.drone_registry"

    @classmethod
    def all(cls) -> list:
        return [
            cls.DRONE_MANAGER,
            cls.CHARGING_MANAGER,
            cls.PORT_MANAGER,
            cls.DRONE_REGISTRY,
        ]


class DroneManagerActions:
    REQUEST_TAKEOFF = "request_takeoff"
    REQUEST_LANDING = "request_landing"
