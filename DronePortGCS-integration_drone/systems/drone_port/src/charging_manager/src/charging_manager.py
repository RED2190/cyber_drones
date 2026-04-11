"""
ChargingManager — логика зарядки дронов.
"""
import datetime
import threading
import time
from typing import Dict, Any
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.charging_manager.topics import ComponentTopics
from systems.drone_port.src.drone_registry.topics import DroneRegistryActions


class ChargingManager(BaseComponent):
    def __init__(
        self,
        component_id: str,
        name: str,
        bus: SystemBus,
    ):
        super().__init__(
            component_id=component_id,
            component_type="drone_port",
            topic=ComponentTopics.CHARGING_MANAGER,
            bus=bus,
        )
        self.name = name

    def _register_handlers(self) -> None:
        self.register_handler("start_charging", self._handle_start_charging)

    def _simulate_charging(self, drone_id: str, battery: float) -> None:
        current_battery = max(0.0, min(float(battery), 100.0))

        while current_battery < 100.0:
            step = min(10.0, 100.0 - current_battery)
            time.sleep(step)
            current_battery += step

            self.bus.publish(
                ComponentTopics.DRONE_REGISTRY,
                {
                    "action": DroneRegistryActions.UPDATE_BATTERY,
                    "payload": {
                        "drone_id": drone_id,
                        "battery": current_battery,
                    },
                    "sender": self.component_id,
                }
            )

    def _handle_start_charging(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запуск зарядки дрона.
        """
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")
        battery = payload.get("battery", 0.0)

        self.bus.publish(
            ComponentTopics.DRONE_REGISTRY,
            {
                "action": DroneRegistryActions.CHARGING_STARTED,
                "payload": {
                    "drone_id": drone_id,
                },
                "sender": self.component_id,
            }
        )

        threading.Thread(
            target=self._simulate_charging,
            args=(drone_id, battery),
            daemon=True,
        ).start()

        return None
