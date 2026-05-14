"""Топики и actions для Orchestrator в составе drone_port."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    ORCHESTRATOR = f"{_P}components.orchestrator"
    DRONE_REGISTRY = f"{_P}components.drone_registry"

    @classmethod
    def all(cls) -> list:
        return [
            cls.ORCHESTRATOR,
            cls.DRONE_REGISTRY,
        ]


class OrchestratorActions:
    GET_AVAILABLE_DRONES = "get_available_drones"
