"""Топики и actions для DroneRegistry в составе drone_port."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="SYSTEM_NAME",
    default_system_name="drone_port",
)


class ComponentTopics:
    DRONE_REGISTRY = build_component_topic("registry")
    DRONE_MANAGER = build_component_topic("drone_manager")
    CHARGING_MANAGER = build_component_topic("charging_manager")

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
