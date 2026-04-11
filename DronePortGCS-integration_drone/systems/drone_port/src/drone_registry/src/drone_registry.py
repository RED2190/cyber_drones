"""
DroneRegistry — реестр дронов в Redis.
"""
import datetime
from typing import Dict, Any
import redis
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions


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

        super().__init__(
            component_id=component_id,
            component_type="drone_port",
            topic=RegistryTopics.DRONE_REGISTRY,
            bus=bus,
        )
        self.name = name

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

        self.redis.hset(
            f"drone:{drone_id}",
            mapping={
                "drone_id": drone_id,
                "model": payload.get("model", "unknown"),
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

        return {
            "drones": drones,
            "from": self.component_id
        }

    def _handle_get_drone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload")
        drone_id = payload.get("drone_id")
        drone = self.redis.hgetall(f"drone:{drone_id}")

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

        self.redis.delete(f"drone:{drone_id}")
        return None

    def _handle_charging_started(self, message: Dict[str, Any]) -> None:
        """
        Обновляет статус дрона после начала зарядки.
        """
        payload = message.get("payload")
        drone_id = payload.get("drone_id")

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

        self.redis.hset(
            f"drone:{drone_id}",
            mapping={
                "battery": battery,
                "status": "ready" if battery == 100 else "charging",
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )

        return None
