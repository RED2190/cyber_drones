"""
StateStore — хранение состояния портов в Redis.
"""
import redis
from typing import Dict, Any
from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus
from systems.drone_port.src.state_store.src.ports import DEFAULT_PORTS
from systems.drone_port.src.state_store.topics import ComponentTopics, StateStoreActions


class StateStore(BaseComponent):
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

        for port in DEFAULT_PORTS:
            key = f"port:{port['port_id']}"
            if not self.redis.exists(key):
                self.redis.hset(key, mapping=port)
                
        super().__init__(
            component_id=component_id,
            component_type="drone_port",
            topic=ComponentTopics.STATE_STORE,
            bus=bus,
        )
        self.name = name

    def _register_handlers(self) -> None:
        self.register_handler(StateStoreActions.GET_ALL_PORTS, self._handle_get_all_ports)
        self.register_handler(StateStoreActions.UPDATE_PORT, self._handle_update_port)

    def _handle_get_all_ports(self, message: Dict[str, Any]) -> Dict[str, Any]:
        ports = []
        for port in DEFAULT_PORTS:
            key = f"port:{port['port_id']}"
            port_data = self.redis.hgetall(key)
            if not port_data:
                continue
            ports.append({"port_id": port["port_id"], **port_data})

        return {
            "ports": ports,
        }

    def _handle_update_port(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload")
        port_id = payload.get("port_id")
        drone_id = payload.get("drone_id")
        status = payload.get("status")

        self.redis.hset(
            f"port:{port_id}",
            mapping={
                "drone_id": drone_id or "",
                "status": status,
            },
        )

        return None
