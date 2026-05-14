"""
Топики и actions для Gateway orvd_system.
Поддерживает внешний API Agrodron (v1.*).
"""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    # Внутренний системный топик
    ORVD_SYSTEM = f"{_P}systems.orvd_system"

    # ВНЕШНИЙ API топик (Agrodron контракт)
    ORVD_EXTERNAL = os.environ.get(
        "ORVD_EXTERNAL_TOPIC",
        "v1.ORVD.ORVD001.main",
    )


class ComponentTopics:
    ORVD_COMPONENT = f"{_P}components.orvd_component"

    @classmethod
    def all(cls) -> list:
        return [cls.ORVD_COMPONENT]


class GatewayActions:

    # внутренние
    REGISTER_DRONE = "register_drone"
    REGISTER_MISSION = "register_mission"
    AUTHORIZE_MISSION = "authorize_mission"
    REQUEST_TAKEOFF = "request_takeoff"
    REVOKE_TAKEOFF = "revoke_takeoff"
    SEND_TELEMETRY = "send_telemetry"
    REQUEST_TELEMETRY = "request_telemetry"
    ADD_NO_FLY_ZONE = "add_no_fly_zone"
    REMOVE_NO_FLY_ZONE = "remove_no_fly_zone"
    GET_HISTORY = "get_history"