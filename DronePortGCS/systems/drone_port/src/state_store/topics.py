"""Топики и actions для StateStore в составе drone_port."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="SYSTEM_NAME",
    default_system_name="drone_port",
)


class ComponentTopics:
    STATE_STORE = build_component_topic("state_store")

    @classmethod
    def all(cls) -> list:
        return [
            cls.STATE_STORE,
        ]


class StateStoreActions:
    GET_ALL_PORTS = "get_all_ports"
    UPDATE_PORT = "update_port"
