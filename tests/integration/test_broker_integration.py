"""
Интеграционные тесты брокера (SystemBus) через Kafka/MQTT.

Требуют: docker-up (kafka или mosquitto). Без брокера тесты пропускаются.
"""
import os
import time
import socket
import uuid
import pytest


def _broker_available(retries=5, delay=2):
    bt = (os.environ.get("BROKER_TYPE", "kafka") or "kafka").lower().strip().split("#")[0].strip()
    host = os.environ.get("BROKER_HOST", "localhost")
    port_val = os.environ.get("MQTT_PORT", "1883") if bt == "mqtt" else os.environ.get("KAFKA_PORT", "9092")
    port = int(port_val)
    for _ in range(retries):
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(delay)
    return False


def _ensure_broker_env():
    bt = (os.environ.get("BROKER_TYPE") or "kafka").lower().strip().split("#")[0].strip()
    host = os.environ.get("BROKER_HOST", "localhost")
    kafka_port = os.environ.get("KAFKA_PORT", "9092")
    mqtt_port = os.environ.get("MQTT_PORT", "1883")
    if not os.environ.get("BROKER_USER") and os.environ.get("ADMIN_USER"):
        os.environ["BROKER_USER"] = os.environ["ADMIN_USER"]
    if not os.environ.get("BROKER_PASSWORD") and os.environ.get("ADMIN_PASSWORD"):
        os.environ["BROKER_PASSWORD"] = os.environ["ADMIN_PASSWORD"]
    if bt == "kafka":
        os.environ["BROKER_TYPE"] = "kafka"
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", f"{host}:{kafka_port}"
        )
    else:
        os.environ["BROKER_TYPE"] = "mqtt"
        os.environ["MQTT_BROKER"] = os.environ.get("MQTT_BROKER", host)
        os.environ["MQTT_PORT"] = str(mqtt_port)


@pytest.fixture(scope="module")
def system_bus():
    if not _broker_available():
        pytest.skip(
            f"Broker at {os.environ.get('BROKER_HOST', 'localhost')} not available. Run: make docker-up"
        )
    _ensure_broker_env()
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id=f"integration_test_{uuid.uuid4().hex[:8]}")
    bus.start()
    time.sleep(2)
    yield bus
    bus.stop()


def test_create_system_bus_start_stop():
    """Реальная шина создаётся, запускается и останавливается без ошибок."""
    if not _broker_available():
        pytest.skip("Broker not available. Run: make docker-up")
    _ensure_broker_env()
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id=f"integration_start_stop_{uuid.uuid4().hex[:8]}")
    bus.start()
    time.sleep(1)
    bus.stop()


def test_publish_subscribe_roundtrip(system_bus):
    """Публикация в топик и получение сообщения через подписку (два клиента)."""
    topic = f"integration.test.roundtrip.{uuid.uuid4().hex}"
    received = []

    def on_message(msg):
        received.append(msg)

    system_bus.subscribe(topic, on_message)
    time.sleep(1)

    message = {"action": "test", "sender": "integration_test", "payload": {"value": 42}}
    ok = system_bus.publish(topic, message)
    assert ok is True

    # Ждём доставки
    for _ in range(25):
        if received:
            break
        time.sleep(0.2)

    assert len(received) == 1
    assert received[0]["action"] == "test"
    assert received[0]["payload"]["value"] == 42

    system_bus.unsubscribe(topic)


def test_request_without_responder_returns_none(system_bus):
    """request() к топику без подписчика возвращает None (таймаут)."""
    topic = f"integration.test.nobody.{uuid.uuid4().hex}"
    response = system_bus.request(
        topic,
        {"action": "ping", "sender": "test", "payload": {}},
        timeout=2.0,
    )
    assert response is None
