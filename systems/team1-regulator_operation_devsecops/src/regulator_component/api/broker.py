import asyncio
import json
import logging
import paho.mqtt.client as mqtt
from config import Config
import os

logger = logging.getLogger(__name__)

MQTT_HOST = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

class BrokerService:
    async def send_and_wait(self, request_topic, response_topic, payload):
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        def on_connect(c, userdata, flags, reason_code, properties):
            c.subscribe(response_topic)
            c.publish(request_topic, json.dumps(payload))

        def on_message(c, userdata, msg):
            if str(msg.topic) == response_topic and not future.done():
                try:
                    data = json.loads(msg.payload)
                    loop.call_soon_threadsafe(future.set_result, data)
                except Exception as e:
                    loop.call_soon_threadsafe(future.set_exception, e)

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()

        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            return {"error": "timeout"}
        finally:
            client.loop_stop()
            client.disconnect()
