"""
PortManager — управление посадочными площадками.
"""
import datetime
from typing import Dict, Any, List
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.port_manager.topics import ComponentTopics, PortManagerActions
from systems.drone_port.src.state_store.topics import StateStoreActions


class PortManager(BaseComponent):
    def __init__(
        self,
        component_id: str,
        name: str,
        bus: SystemBus,
    ):
        super().__init__(
            component_id=component_id,
            component_type="drone_port",
            topic=ComponentTopics.PORT_MANAGER,
            bus=bus,
        )
        self.name = name

    def _register_handlers(self) -> None:
        self.register_handler(PortManagerActions.REQUEST_LANDING, self._handle_request_landing)
        self.register_handler(PortManagerActions.FREE_SLOT, self._handle_free_slot)
        self.register_handler(PortManagerActions.GET_PORT_STATUS, self._handle_get_port_status)

    def _handle_request_landing(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")

        response = self.bus.request(
            ComponentTopics.STATE_STORE,
            {
                "action": StateStoreActions.GET_ALL_PORTS,
                "payload": {},
            },
            timeout=3.0,
        )
        ports = (response or {}).get("ports", [])

        for port in ports:
            if not port.get("drone_id"):
                self.bus.publish(
                    ComponentTopics.STATE_STORE,
                    {
                        "action": StateStoreActions.UPDATE_PORT,
                        "payload": {
                            "port_id": port["port_id"],
                            "drone_id": drone_id,
                            "status": "reserved",
                        },
                    }
                )

                return {
                    "port_id": port["port_id"],
                }

        return {
            "error": "No free ports"
        }

    def _handle_free_slot(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Освободить порт."""
        payload = message.get("payload", {})
        port_id = payload.get("port_id")
        
        self.bus.publish(
            ComponentTopics.STATE_STORE,
            {
                "action": StateStoreActions.UPDATE_PORT,
                "payload": {
                    "port_id": port_id,
                    "drone_id": None,
                    "status": "free",
                },
            }
        )
        
        return None

    def _handle_get_port_status(self, message: Dict[str, Any]) -> Dict[str, Any]:
        response = self.bus.request(
            ComponentTopics.STATE_STORE,
            {
                "action": StateStoreActions.GET_ALL_PORTS,
                "payload": {},
            },
            timeout=3.0,
        )

        return {
            "ports": (response or {}).get("ports", []),
        }
