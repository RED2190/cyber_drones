"""Топики и actions для DroneManager в составе drone_port."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="SYSTEM_NAME",
    default_system_name="drone_port",
)


class ComponentTopics:
    DRONE_MANAGER = build_component_topic("drone_manager")
    CHARGING_MANAGER = build_component_topic("charging_manager")
    PORT_MANAGER = build_component_topic("port_manager")
    DRONE_REGISTRY = build_component_topic("registry")

    @classmethod
    def all(cls) -> list:
        return [
            cls.DRONE_MANAGER,
            cls.CHARGING_MANAGER,
            cls.PORT_MANAGER,
            cls.DRONE_REGISTRY,
        ]


class DroneManagerActions:
    REQUEST_LANDING = "request_landing"
    REQUEST_TAKEOFF = "request_takeoff"
    REQUEST_CHARGING = "request_charging"
