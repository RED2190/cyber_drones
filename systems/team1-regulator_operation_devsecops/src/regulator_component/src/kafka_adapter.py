# kafka_adapter.py
# NOTE: В среде интегратора реальный KafkaSystemBus берётся из broker.kafka (SDK).
# Здесь — адаптер-заглушка для локальной разработки и тестов без SDK.
import asyncio
import json
import logging
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)


class KafkaBrokerAdapter:
    """
    Локальная заглушка Kafka-адаптера.
    В среде интегратора заменяется на реальный KafkaSystemBus из broker.kafka.
    """
    def __init__(self, bootstrap_servers: str, client_id: str = "regulator",
                 group_id: str = None, username: str = None, password: str = None):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.group_id = group_id
        self._handlers: Dict[str, Callable] = {}
        self._running = False

    async def connect(self):
        logger.info(f"[KafkaBrokerAdapter stub] connect() bootstrap={self.bootstrap_servers}")
        self._running = True

    async def publish(self, topic: str, message: Any):
        if isinstance(message, dict):
            payload = json.dumps(message)
        else:
            payload = str(message)
        logger.info(f"[KafkaBrokerAdapter stub] publish → {topic}: {payload[:200]}")

    async def subscribe(self, topic: str, handler: Callable):
        self._handlers[topic] = handler
        logger.info(f"[KafkaBrokerAdapter stub] subscribed → {topic}")

    async def start_consuming(self):
        logger.info("[KafkaBrokerAdapter stub] start_consuming() — stub, no real messages")

    async def close(self):
        self._running = False
        logger.info("[KafkaBrokerAdapter stub] closed")
