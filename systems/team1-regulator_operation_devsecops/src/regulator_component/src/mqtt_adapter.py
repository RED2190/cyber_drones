# mqtt_adapter.py
# NOTE: В среде интегратора реальный MQTTSystemBus берётся из broker.mqtt (SDK).
# Здесь — адаптер-заглушка для локальной разработки и тестов без SDK.
import asyncio
import json
import logging
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)


class MQTTBrokerAdapter:
    """
    Локальная заглушка MQTT-адаптера.
    В среде интегратора заменяется на реальный MQTTSystemBus из broker.mqtt.
    """
    def __init__(self, broker: str = "localhost", port: int = 1883,
                 client_id: str = "regulator", username: str = None,
                 password: str = None, qos: int = 1):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self._handlers: Dict[str, Callable] = {}
        self._running = False

    async def connect(self):
        logger.info(f"[MQTTBrokerAdapter stub] connect() broker={self.broker}:{self.port}")
        self._running = True

    async def publish(self, topic: str, message: Any):
        if isinstance(message, dict):
            payload = json.dumps(message)
        else:
            payload = str(message)
        logger.info(f"[MQTTBrokerAdapter stub] publish → {topic}: {payload[:200]}")

    async def subscribe(self, topic: str, handler: Callable):
        self._handlers[topic] = handler
        logger.info(f"[MQTTBrokerAdapter stub] subscribed → {topic}")

    async def start_consuming(self):
        logger.info("[MQTTBrokerAdapter stub] start_consuming() — stub, no real messages")

    async def close(self):
        self._running = False
        logger.info("[MQTTBrokerAdapter stub] closed")
