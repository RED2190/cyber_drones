"""Топики и actions для Orchestrator в составе drone_port."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="SYSTEM_NAME",
    default_system_name="drone_port",
)


class ComponentTopics:
    ORCHESTRATOR = build_component_topic("orchestrator")
    DRONE_REGISTRY = build_component_topic("registry")

    @classmethod
    def all(cls) -> list:
        return [
            cls.ORCHESTRATOR,
            cls.DRONE_REGISTRY,
        ]


class OrchestratorActions:
    GET_AVAILABLE_DRONES = "get_available_drones"
