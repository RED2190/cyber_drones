import asyncio
import json
import logging
from typing import Callable, Dict, Any
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class BrokerClient:
    def __init__(self, url: str, exchange: str):
        self.host = url
        self.handlers: Dict[str, Callable] = {}
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._loop = None
        self._connected = asyncio.Event()

    async def connect(self):
        self._loop = asyncio.get_event_loop()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(self.host, 1883, 60)
        self._client.loop_start()
        await asyncio.wait_for(self._connected.wait(), timeout=10)
        logger.info(f"Connected to MQTT broker at {self.host}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self._loop.call_soon_threadsafe(self._connected.set)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        handler = self.handlers.get(topic)
        if handler:
            try:
                data = json.loads(msg.payload)
                asyncio.run_coroutine_threadsafe(handler(topic, data), self._loop)
            except Exception as e:
                logger.error(f"Error handling {topic}: {e}", exc_info=True)

    async def publish(self, topic: str, message: Any):
        payload = json.dumps(message) if isinstance(message, dict) else str(message)
        self._client.publish(topic, payload)
        logger.info(f"Published to {topic}")

    async def subscribe(self, topic: str, handler: Callable):
        self.handlers[topic] = handler
        self._client.subscribe(topic)
        logger.info(f"Subscribed to {topic}")

    async def start_consuming(self):
        logger.info("MQTT paho client consuming messages...")

    async def close(self):
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("MQTT broker client closed.")