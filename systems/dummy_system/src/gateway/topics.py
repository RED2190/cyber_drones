"""Топики и actions для Gateway dummy_system."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    DUMMY_SYSTEM = f"{_P}systems.dummy_system"


class ComponentTopics:
    DUMMY_COMPONENT_A = f"{_P}components.dummy_component_a"
    DUMMY_COMPONENT_B = f"{_P}components.dummy_component_b"

    @classmethod
    def all(cls) -> list:
        return [cls.DUMMY_COMPONENT_A, cls.DUMMY_COMPONENT_B]


class GatewayActions:
    """Actions, доступные извне через systems.dummy_system."""
    ECHO = "echo"
    INCREMENT = "increment"
    GET_STATE = "get_state"
    GET_DATA = "get_data"
