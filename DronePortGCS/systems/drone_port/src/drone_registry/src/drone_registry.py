"""
DroneRegistry — реестр дронов в Redis.
"""
import datetime
import logging
from typing import Dict, Any
import redis
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions

logger = logging.getLogger(__name__)


DEFAULT_DEMO_DRONE_ID = "drone_001"
DEFAULT_DEMO_DRONE_MODEL = "AgroDron"
DEFAULT_DEMO_DRONE_PORT_ID = "P-01"
DEFAULT_DEMO_DRONE_BATTERY = "100"


class DroneRegistry(BaseComponent):
    def __init__(
        self,
        component_id: str,
        name: str,
        bus: SystemBus,
        redis_host: str = "redis",
        redis_port: int = 6379,
    ):
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self._seed_default_demo_drone()

        super().__init__(
            component_id=component_id,
            component_type="drone_port",
            topic=RegistryTopics.DRONE_REGISTRY,
            bus=bus,
        )
        self.name = name

    def _seed_default_demo_drone(self) -> None:
        key = f"drone:{DEFAULT_DEMO_DRONE_ID}"
        if self.redis.hgetall(key):
            return

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.redis.hset(
            key,
            mapping={
                "drone_id": DEFAULT_DEMO_DRONE_ID,
                "model": DEFAULT_DEMO_DRONE_MODEL,
                "port_id": DEFAULT_DEMO_DRONE_PORT_ID,
                "battery": DEFAULT_DEMO_DRONE_BATTERY,
                "status": "ready",
                "registered_at": now,
                "updated_at": now,
            },
        )

    def _register_handlers(self) -> None:
        self.register_handler(DroneRegistryActions.REGISTER_DRONE, self._handle_register_drone)
        self.register_handler(DroneRegistryActions.GET_DRONE, self._handle_get_drone)
        self.register_handler(DroneRegistryActions.GET_AVAILABLE_DRONES, self._handle_get_available_drones)
        self.register_handler(DroneRegistryActions.DELETE_DRONE, self._handle_delete_drone)
        self.register_handler(DroneRegistryActions.CHARGING_STARTED, self._handle_charging_started)
        self.register_handler(DroneRegistryActions.UPDATE_BATTERY, self._handle_update_battery)

    def _handle_register_drone(self, message: Dict[str, Any]) -> None:
        """
        Регистрация нового дрона.
        """
        payload = message.get("payload")
        drone_id = payload.get("drone_id")
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        logger.info("[%s] register_drone drone_id=%s payload=%r", self.component_id, drone_id, payload)

        self.redis.hset(
            f"drone:{drone_id}",
            mapping={
                "drone_id": drone_id,
                "model": payload.get("model", "unknown"),
                "port_id": payload.get("port_id", ""),
                "battery": "unknown",
                "status": "new",
                "registered_at": now,
                "updated_at": now,
            },
        )
        
        return None

    def _handle_get_available_drones(self, message: Dict[str, Any]) -> Dict[str, Any]:
        drones = []
        for key in self.redis.keys("drone:*"):
            drone = self.redis.hgetall(key)
            if drone and drone.get("status") == "ready":
                drones.append(drone)
        logger.info("[%s] get_available_drones count=%s", self.component_id, len(drones))

        return {
            "drones": drones,
            "from": self.component_id
        }

    def _handle_get_drone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload")
        drone_id = payload.get("drone_id")
        drone = self.redis.hgetall(f"drone:{drone_id}")
        logger.info("[%s] get_drone drone_id=%s found=%s", self.component_id, drone_id, bool(drone))

        if not drone:
            return {
                "error": "Drone not found",
                "from": self.component_id,
            }

        return {
            **drone,
            "success": True,
            "from": self.component_id,
        }

    def _handle_delete_drone(self, message: Dict[str, Any]) -> None:
        payload = message.get("payload")
        drone_id = payload.get("drone_id")
        logger.info("[%s] delete_drone drone_id=%s", self.component_id, drone_id)

        self.redis.delete(f"drone:{drone_id}")
        return None

    def _handle_charging_started(self, message: Dict[str, Any]) -> None:
        """
        Обновляет статус дрона после начала зарядки.
        """
        payload = message.get("payload")
        drone_id = payload.get("drone_id")
        logger.info("[%s] charging_started drone_id=%s", self.component_id, drone_id)

        self.redis.hset(
            f"drone:{drone_id}",
            mapping={
                "status": "charging",
            },
        )

        return None

    def _handle_update_battery(self, message: Dict[str, Any]) -> None:
        """
        Обновляет уровень заряда дрона.
        """
        payload = message.get("payload")
        drone_id = payload.get("drone_id")
        battery = payload.get("battery")
        logger.info("[%s] update_battery drone_id=%s battery=%s", self.component_id, drone_id, battery)

        self.redis.hset(
            f"drone:{drone_id}",
            mapping={
                "battery": battery,
                "status": "ready" if battery == 100 else "charging",
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )

        return None
