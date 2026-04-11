"""
ChargingManager — логика зарядки дронов.
"""
import datetime
import logging
import threading
import time
from typing import Dict, Any
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.charging_manager.topics import ComponentTopics
from systems.drone_port.src.drone_registry.topics import DroneRegistryActions

logger = logging.getLogger(__name__)


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
        self._charging_update_interval_s = 0.5
        self._charging_rate_pct_per_s = 2.0

    def _register_handlers(self) -> None:
        self.register_handler("start_charging", self._handle_start_charging)

    def _simulate_charging(self, drone_id: str, battery: float) -> None:
        current_battery = max(0.0, min(float(battery), 100.0))
        logger.info("[%s] simulate_charging started drone_id=%s battery=%s", self.component_id, drone_id, current_battery)
        last_update_ts = time.monotonic()
        last_persisted_percent = int(current_battery)

        while current_battery < 100.0:
            remaining = 100.0 - current_battery
            sleep_s = min(
                self._charging_update_interval_s,
                remaining / self._charging_rate_pct_per_s,
            )
            time.sleep(sleep_s)

            now = time.monotonic()
            dt_s = now - last_update_ts
            last_update_ts = now
            # In tests or under scheduler jitter, monotonic time may advance
            # less than the requested sleep interval. Use the intended step so
            # charging progress still moves forward predictably.
            if dt_s < sleep_s:
                dt_s = sleep_s

            current_battery = min(
                100.0,
                current_battery + self._charging_rate_pct_per_s * dt_s,
            )
            current_battery = round(current_battery, 2)
            current_percent = int(current_battery)

            if current_battery < 100.0 and current_percent == last_persisted_percent:
                continue

            persisted_battery = 100.0 if current_battery >= 100.0 else float(current_percent)
            last_persisted_percent = int(persisted_battery)

            self.bus.publish(
                ComponentTopics.DRONE_REGISTRY,
                {
                    "action": DroneRegistryActions.UPDATE_BATTERY,
                    "payload": {
                        "drone_id": drone_id,
                        "battery": persisted_battery,
                    },
                    "sender": self.component_id,
                }
            )
            logger.info("[%s] simulate_charging update drone_id=%s battery=%s", self.component_id, drone_id, persisted_battery)

    def _handle_start_charging(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запуск зарядки дрона.
        """
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")
        battery = payload.get("battery", 0.0)
        logger.info("[%s] start_charging drone_id=%s battery=%s", self.component_id, drone_id, battery)

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
