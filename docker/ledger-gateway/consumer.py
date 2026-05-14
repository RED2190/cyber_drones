#!/usr/bin/env python3
"""
Ledger Gateway — слушает топик components.ledger через Kafka/MQTT,
транслирует вызовы invoke/query в Fabric REST Proxy (Go) по HTTP.
"""
import os
import sys
import json
import signal
import time
import urllib.request
import urllib.error

LEDGER_TOPIC = "components.ledger"
FABRIC_PROXY_URL = os.environ.get("FABRIC_PROXY_URL", "http://fabric-proxy:3000")


def call_fabric_proxy(endpoint: str, payload: dict) -> dict:
    url = f"{FABRIC_PROXY_URL}/api/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"success": True, "payload": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body)
        except Exception:
            err = {"error": body or str(e)}
        return {"success": False, "payload": err}
    except Exception as e:
        return {"success": False, "payload": {"error": str(e)}}


def handle_message(message: dict) -> dict:
    action = message.get("action", "")
    payload = message.get("payload", {})

    fabric_payload = {
        "channel": payload.get("channel", ""),
        "chaincode": payload.get("chaincode", ""),
        "method": payload.get("method", ""),
        "args": payload.get("args", []),
    }

    if action == "invoke":
        return call_fabric_proxy("invoke", fabric_payload)
    elif action == "query":
        return call_fabric_proxy("query", fabric_payload)
    else:
        return {"success": False, "payload": {"error": f"Unknown action: {action}"}}


def run_kafka():
    from kafka import KafkaConsumer, KafkaProducer
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    user = os.environ.get("BROKER_USER", os.environ.get("ADMIN_USER", "admin"))
    pwd = os.environ.get("BROKER_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin123"))

    consumer = KafkaConsumer(
        LEDGER_TOPIC,
        bootstrap_servers=bootstrap,
        group_id="ledger-gateway",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        security_protocol="SASL_PLAINTEXT",
        sasl_mechanism="PLAIN",
        sasl_plain_username=user,
        sasl_plain_password=pwd,
        auto_offset_reset="earliest",
    )

    producer = KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        security_protocol="SASL_PLAINTEXT",
        sasl_mechanism="PLAIN",
        sasl_plain_username=user,
        sasl_plain_password=pwd,
    )

    print(f"[ledger-gateway] Kafka: listening on {LEDGER_TOPIC}")
    for msg in consumer:
        message = msg.value
        reply_to = message.get("reply_to")
        correlation_id = message.get("correlation_id")

        result = handle_message(message)

        if reply_to:
            response = {
                "action": "response",
                "correlation_id": correlation_id,
                **result,
            }
            producer.send(reply_to, response)
            producer.flush()


def run_mqtt():
    import paho.mqtt.client as mqtt
    broker = os.environ.get("MQTT_BROKER", "mosquitto")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    user = os.environ.get("BROKER_USER", os.environ.get("ADMIN_USER", "admin"))
    pwd = os.environ.get("BROKER_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin123"))
    mqtt_topic = LEDGER_TOPIC.replace(".", "/")

    client = mqtt.Client()
    if user and pwd:
        client.username_pw_set(user, pwd)

    def on_message(c, userdata, msg):
        try:
            message = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            print(f"[ledger-gateway] Parse error: {e}", file=sys.stderr)
            return

        reply_to = message.get("reply_to")
        correlation_id = message.get("correlation_id")

        result = handle_message(message)

        if reply_to:
            response = {
                "action": "response",
                "correlation_id": correlation_id,
                **result,
            }
            reply_mqtt = reply_to.replace(".", "/")
            client.publish(reply_mqtt, json.dumps(response))

    client.on_message = on_message
    client.connect(broker, port, keepalive=60)
    client.subscribe(mqtt_topic)
    print(f"[ledger-gateway] MQTT: listening on {mqtt_topic}")
    client.loop_forever()


def wait_for_proxy():
    url = f"{FABRIC_PROXY_URL}/health"
    print(f"[ledger-gateway] Waiting for fabric-proxy at {url}...")
    for i in range(60):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    print("[ledger-gateway] fabric-proxy OK")
                    return
        except Exception:
            pass
        if (i + 1) % 10 == 0 or i == 0:
            print(f"[ledger-gateway] Attempt {i + 1}/60...")
        time.sleep(2)
    print("[ledger-gateway] fabric-proxy unavailable", file=sys.stderr)
    sys.exit(1)


def main():
    broker_type = os.environ.get("BROKER_TYPE", "kafka").lower().strip()

    wait_for_proxy()

    def shutdown(sig, frame):
        print("\n[ledger-gateway] Shutdown")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if broker_type == "mqtt":
        run_mqtt()
    else:
        run_kafka()


if __name__ == "__main__":
    main()
