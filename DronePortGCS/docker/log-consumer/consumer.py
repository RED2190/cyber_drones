#!/usr/bin/env python3
"""Читает логи из logs.application (Kafka/MQTT) и пишет в Elasticsearch."""
import os
import sys
import json
import signal
import time

LOGS_TOPIC = "logs.application"
ES_INDEX = "app-logs"


def get_es_client():
    from elasticsearch import Elasticsearch
    host = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
    port = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
    return Elasticsearch([f"http://{host}:{port}"])


def index_log(es, doc: dict) -> None:
    try:
        es.index(index=ES_INDEX, document=doc)
    except Exception as e:
        print(f"Elasticsearch index error: {e}", file=sys.stderr)


def run_kafka_consumer(es):
    from kafka import KafkaConsumer
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    user = os.environ.get("BROKER_USER", os.environ.get("ADMIN_USER", "admin"))
    pwd = os.environ.get("BROKER_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin123"))
    consumer = KafkaConsumer(
        LOGS_TOPIC,
        bootstrap_servers=bootstrap,
        group_id="log-consumer-elk",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        security_protocol="SASL_PLAINTEXT",
        sasl_mechanism="PLAIN",
        sasl_plain_username=user,
        sasl_plain_password=pwd,
        auto_offset_reset="earliest",
    )
    print(f"[log-consumer] Kafka: reading {LOGS_TOPIC}")
    for msg in consumer:
        index_log(es, msg.value)


def run_mqtt_consumer(es):
    import paho.mqtt.client as mqtt
    broker = os.environ.get("MQTT_BROKER", "mosquitto")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    user = os.environ.get("BROKER_USER", os.environ.get("ADMIN_USER", "admin"))
    pwd = os.environ.get("BROKER_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin123"))
    mqtt_topic = LOGS_TOPIC.replace(".", "/")

    def on_message(client, userdata, msg):
        try:
            doc = json.loads(msg.payload.decode("utf-8"))
            index_log(es, doc)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

    def on_connect(client, userdata, flags, *args):
        # VERSION1: (flags, rc), VERSION2: (flags, reason_code, properties)
        reason_code = args[0] if args else 0
        rc = getattr(reason_code, "value", reason_code)
        if rc == 0:
            client.subscribe(mqtt_topic, qos=0)
            print(f"[log-consumer] MQTT: subscribed to {mqtt_topic}")

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    if user and pwd:
        client.username_pw_set(user, pwd)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker, port, keepalive=60)
    print(f"[log-consumer] MQTT: connecting to {broker}:{port}, topic {mqtt_topic}")
    client.loop_forever()


def main():
    broker_type = os.environ.get("BROKER_TYPE", "kafka").lower().strip()
    host = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
    port = os.environ.get("ELASTICSEARCH_PORT", "9200")
    print(f"[log-consumer] Waiting for Elasticsearch at {host}:{port}...")
    es = get_es_client()
    max_retries = 90  # 3 min at 2s interval (ES может долго стартовать на Mac)
    last_err = None
    for i in range(max_retries):
        try:
            if es.ping():
                break
            last_err = "ping() returned False"
            if (i + 1) % 10 == 0 or i == 0:
                print(f"[log-consumer] Attempt {i + 1}/{max_retries}...", file=sys.stderr)
        except Exception as e:
            last_err = e
            if (i + 1) % 10 == 0 or i == 0:
                print(f"[log-consumer] Attempt {i + 1}/{max_retries}: {e}", file=sys.stderr)
        time.sleep(2)
    else:
        print(f"Elasticsearch unavailable (last: {last_err})", file=sys.stderr)
        sys.exit(1)
    print("[log-consumer] Elasticsearch OK")

    def shutdown(sig, frame):
        print("\n[log-consumer] Shutdown")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if broker_type == "mqtt":
        run_mqtt_consumer(es)
    else:
        run_kafka_consumer(es)


if __name__ == "__main__":
    main()
