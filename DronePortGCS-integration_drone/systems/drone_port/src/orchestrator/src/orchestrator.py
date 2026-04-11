"""
Orchestrator — взаимодействие с Эксплуатантом и SITL.
"""
import datetime
from typing import Dict, Any
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions
from systems.drone_port.src.orchestrator.topics import OrchestratorActions
from systems.drone_port.src.orchestrator.topics import ComponentTopics as OrchestratorTopics


class Orchestrator(BaseComponent):
    """
    Перенаправляет запросы от Эксплуатанта в DroneRegistry.
    """
    
    def __init__(
        self,
        component_id: str,
        name: str,
        bus: SystemBus,
    ):
        super().__init__(
            component_id=component_id,
            component_type="drone_port",
            topic=OrchestratorTopics.ORCHESTRATOR,
            bus=bus,
        )
        self.name = name

    def _register_handlers(self) -> None:
        self.register_handler(OrchestratorActions.GET_AVAILABLE_DRONES, self._handle_get_available_drones)

    def _handle_get_available_drones(self, message: Dict[str, Any]) -> Dict[str, Any]:
        response = self.bus.request(
            RegistryTopics.DRONE_REGISTRY,
            {
                "action": DroneRegistryActions.GET_AVAILABLE_DRONES,
                "payload": {},
            },
            timeout=5.0,
        )

        if response and response.get("success"):
            return {
                "drones": response.get("payload", {}).get("drones", []),
                "from": self.component_id,
            }

        return {
            "error": "Failed to get available drones",
            "from": self.component_id,
        }
