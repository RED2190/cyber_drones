"""Топики и actions для ChargingManager в составе drone_port"""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="SYSTEM_NAME",
    default_system_name="drone_port",
)


class ComponentTopics:
    CHARGING_MANAGER = build_component_topic("charging_manager")
    DRONE_REGISTRY = build_component_topic("registry")

    @classmethod
    def all(cls) -> list:
        return [
            cls.CHARGING_MANAGER,
            cls.DRONE_REGISTRY,
        ]


class ChargingManagerActions:
    START_CHARGING = "start_charging"
    GET_CHARGING_STATUS = "get_charging_status"
