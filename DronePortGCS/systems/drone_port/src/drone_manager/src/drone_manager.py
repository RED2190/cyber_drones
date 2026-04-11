"""
DroneManager — взаимодействие с физическими дронами.
"""
import logging
import os
from typing import Dict, Any
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.charging_manager.topics import ComponentTopics as ChargingTopics, ChargingManagerActions
from systems.drone_port.src.drone_manager.topics import ComponentTopics as DroneManagerTopics, DroneManagerActions
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions
from systems.drone_port.src.port_manager.topics import ComponentTopics as PortTopics, PortManagerActions

logger = logging.getLogger(__name__)


class ExternalTopics:
    SITL_HOME = (os.environ.get("SITL_HOME_TOPIC") or "sitl-drone-home").strip()


def _build_sitl_home_message(drone_id: str, drone_port: Dict[str, Any] | None) -> Dict[str, Any]:
    return {
        "drone_id": drone_id,
        "home_lat": float((drone_port or {}).get("lat") or 0.0),
        "home_lon": float((drone_port or {}).get("lon") or 0.0),
        "home_alt": float((drone_port or {}).get("alt") or 0.0),
    }


def _extract_payload(response: Dict[str, Any] | None) -> Dict[str, Any]:
    """Поддерживаем и bus-ответ с payload, и старые плоские моки."""
    if not response:
        return {}
    payload = response.get("payload")
    if isinstance(payload, dict):
        return payload
    return response


def _parse_battery_value(raw_value: Any) -> float | None:
    if raw_value in (None, "", "unknown"):
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _drone_id_from_sender(sender: Any) -> str | None:
    if not isinstance(sender, str):
        return None
    parts = [part for part in sender.split(".") if part]
    if len(parts) < 4:
        return None
    return parts[2] or None


class DroneManager(BaseComponent):
    """
    Передает запросы:
    - от дронов к PortManager (landing/takeoff)
    - от дронов к ChargingManager (charging)
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
            topic=DroneManagerTopics.DRONE_MANAGER,
            bus=bus,
        )
        self._drone_battery = {}
        self.name = name

    def _register_handlers(self) -> None:
        self.register_handler(DroneManagerActions.REQUEST_LANDING, self._handle_landing)
        self.register_handler(DroneManagerActions.REQUEST_TAKEOFF, self._handle_takeoff)

    def _handle_landing(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запрос на посадку от дрона.
        """
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id") or _drone_id_from_sender(message.get("sender"))
        model = payload.get("model", "unknown")
        battery = _parse_battery_value(payload.get("battery"))
        logger.info(
            "[%s] request_landing drone_id=%s model=%s battery=%s sender=%s",
            self.component_id,
            drone_id,
            model,
            battery,
            message.get("sender"),
        )

        response = self.bus.request(
            PortTopics.PORT_MANAGER,
            {
                "action": PortManagerActions.REQUEST_LANDING,
                "payload": {
                    "drone_id": drone_id
                },
                "sender": self.component_id,
            },
            timeout=3.0
        )
        response_payload = _extract_payload(response)
        logger.info("[%s] request_landing port_manager response=%r", self.component_id, response)

        if response and response_payload.get("port_id"):
            self.bus.publish(
                RegistryTopics.DRONE_REGISTRY,
                {
                    "action": DroneRegistryActions.REGISTER_DRONE,
                    "payload": {
                        "drone_id": drone_id,
                        "model": model,
                        "port_id": response_payload.get("port_id"),
                    },
                    "sender": self.component_id,
                }
            )

            if battery is not None:
                self.bus.publish(
                    RegistryTopics.DRONE_REGISTRY,
                    {
                        "action": DroneRegistryActions.UPDATE_BATTERY,
                        "payload": {
                            "drone_id": drone_id,
                            "battery": battery,
                        },
                        "sender": self.component_id,
                    }
                )

                if battery < 100.0:
                    self.bus.publish(
                        ChargingTopics.CHARGING_MANAGER,
                        {
                            "action": ChargingManagerActions.START_CHARGING,
                            "payload": {
                                "drone_id": drone_id,
                                "battery": battery,
                            },
                            "sender": self.component_id,
                        }
                    )

            port_id = response_payload.get("port_id")
            logger.info("[%s] request_landing approved drone_id=%s port_id=%s", self.component_id, drone_id, port_id)
            return {
                "approved": True,
                "port_id": port_id,
                "drone_id": drone_id,
                "from": self.component_id,
            }
        
        return {
            "error": "No free ports",
            "from": self.component_id
        }

    def _handle_takeoff(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запрос на взлет от дрона.
        """
        payload = message.get("payload") or {}
        drone_id = payload.get("drone_id") or _drone_id_from_sender(message.get("sender"))
        logger.info(
            "[%s] request_takeoff drone_id=%s payload=%r sender=%s",
            self.component_id,
            drone_id,
            payload,
            message.get("sender"),
        )
        port_response = self.bus.request(
            PortTopics.PORT_MANAGER,
            {
                "action": PortManagerActions.GET_PORT_STATUS,
                "payload": {},
            },
            timeout=3.0,
        )
        ports = _extract_payload(port_response).get("ports", [])
        logger.info("[%s] request_takeoff ports_response=%r", self.component_id, port_response)
        drone_port = next(
            (port for port in ports if port.get("drone_id") == drone_id),
            None,
        )

        response = self.bus.request(
            RegistryTopics.DRONE_REGISTRY,
            {
                "action": DroneRegistryActions.GET_DRONE,
                "payload": {
                    "drone_id": drone_id
                },
                "sender": self.component_id,
            }
        )
        response_payload = _extract_payload(response)
        logger.info("[%s] request_takeoff registry response=%r", self.component_id, response)

        if response and response.get("success"):
            battery = _parse_battery_value(response_payload.get("battery"))
            port_id = response_payload.get("port_id") or (drone_port or {}).get("port_id")

            if battery is None:
                return {
                    "error": "Battery level is unknown",
                    "from": self.component_id,
                }

            if battery > 60.0:
                logger.info(
                    "[%s] request_takeoff approved drone_id=%s battery=%s port_id=%s sitl_home=%r",
                    self.component_id,
                    drone_id,
                    battery,
                    port_id,
                    _build_sitl_home_message(drone_id, drone_port),
                )
                self.bus.publish(
                    PortTopics.PORT_MANAGER,
                    {
                        "action": PortManagerActions.FREE_SLOT,
                        "payload": {
                            "drone_id": drone_id,
                            "port_id": port_id,
                        },
                        "sender": self.component_id,
                    }
                )

                self.bus.publish(ExternalTopics.SITL_HOME, _build_sitl_home_message(drone_id, drone_port))

                return {
                    "approved": True,
                    "battery": battery,
                    "port_id": port_id,
                    "drone_id": drone_id,
                    "port_coordinates": {
                        "lat": (drone_port or {}).get("lat"),
                        "lon": (drone_port or {}).get("lon"),
                    },
                    "from": self.component_id,
                }

            return {
                "error": "Not enough battery for takeoff",
                "from": self.component_id
            }

        return {
            "error": "Failed to get drone information",
            "from": self.component_id
        }
