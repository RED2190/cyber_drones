"""Топики и внешние actions для gateway DronePort."""

import os

from ..drone_manager.topics import DroneManagerActions
from ..orchestrator.topics import OrchestratorActions


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    DRONE_PORT = f"{_P}systems.drone_port"


class ComponentTopics:
    CHARGING_MANAGER = f"{_P}components.charging_manager"
    DRONE_MANAGER = f"{_P}components.drone_manager"
    DRONE_REGISTRY = f"{_P}components.drone_registry"
    ORCHESTRATOR = f"{_P}components.orchestrator"
    PORT_MANAGER = f"{_P}components.port_manager"
    STATE_STORE = f"{_P}components.state_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.CHARGING_MANAGER,
            cls.DRONE_MANAGER,
            cls.DRONE_REGISTRY,
            cls.ORCHESTRATOR,
            cls.PORT_MANAGER,
            cls.STATE_STORE,
        ]


class GatewayActions:
    GET_AVAILABLE_DRONES = OrchestratorActions.GET_AVAILABLE_DRONES
    REQUEST_LANDING = DroneManagerActions.REQUEST_LANDING
    REQUEST_TAKEOFF = DroneManagerActions.REQUEST_TAKEOFF
