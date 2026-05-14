"""Топики и actions для ChargingManager в составе drone_port."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    CHARGING_MANAGER = f"{_P}components.charging_manager"
    DRONE_REGISTRY = f"{_P}components.drone_registry"

    @classmethod
    def all(cls) -> list:
        return [
            cls.CHARGING_MANAGER,
            cls.DRONE_REGISTRY,
        ]


class ChargingManagerActions:
    START_CHARGING = "start_charging"
    GET_CHARGING_STATUS = "get_charging_status"
