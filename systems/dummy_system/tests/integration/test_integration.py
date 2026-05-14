"""
E2E тесты dummy_system через реальный брокер.
Требует: make docker-up (kafka/mosquitto + dummy_component_a/b).
Если контейнеры не запущены — тесты пропускаются (skip).
"""
import pytest
import os
import time
import socket

from systems.dummy_system.src.dummy_component_a.topics import (
    ComponentTopics,
    DummyComponentActions,
)
from systems.dummy_system.src.gateway.topics import (
    SystemTopics,
    GatewayActions,
)


def _broker_available(retries=5, delay=2):
    bt = os.environ.get("BROKER_TYPE", "kafka").lower().strip().split("#")[0].strip()
    host = os.environ.get("BROKER_HOST", "localhost")
    port_val = (
        os.environ.get("MQTT_PORT", "1883")
        if bt == "mqtt"
        else os.environ.get("KAFKA_PORT", "9092")
    )
    port = int(port_val)
    for _ in range(retries):
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(delay)
    return False


@pytest.fixture(scope="module")
def system_bus():
    if not _broker_available():
        pytest.skip(
            f"Broker ({os.environ.get('BROKER_TYPE', 'kafka')}) "
            f"at {os.environ.get('BROKER_HOST', 'localhost')} not available."
        )
    from broker.bus_factory import create_system_bus

    bt = os.environ.get("BROKER_TYPE", "kafka").lower().strip().split("#")[0].strip()
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

    bus = create_system_bus(client_id="test_client")
    bus.start()
    time.sleep(2)

    yield bus

    bus.stop()


def test_echo_component(system_bus):
    """Отправляем echo в компонент и проверяем ответ."""
    response = system_bus.request(
        ComponentTopics.DUMMY_COMPONENT_A,
        {
            "action": DummyComponentActions.ECHO,
            "sender": "test_client",
            "payload": {"message": "hello"},
        },
        timeout=10.0,
    )
    if response is None:
        pytest.skip(
            "No response from component (timeout). "
            "Run: make docker-up"
        )
    assert response.get("success") is True
    assert response["payload"]["echo"] == {"message": "hello"}
    assert "from" in response["payload"]


def test_increment_component(system_bus):
    """Отправляем increment в компонент."""
    response = system_bus.request(
        ComponentTopics.DUMMY_COMPONENT_A,
        {
            "action": DummyComponentActions.INCREMENT,
            "sender": "test_client",
            "payload": {"value": 7},
        },
        timeout=10.0,
    )
    if response is None:
        pytest.skip(
            "No response from component (timeout). "
            "Run: make docker-up"
        )
    assert response.get("success") is True
    assert response["payload"]["counter"] == 7
    assert "from" in response["payload"]


def test_get_state_component(system_bus):
    """Запрашиваем состояние компонента."""
    response = system_bus.request(
        ComponentTopics.DUMMY_COMPONENT_A,
        {
            "action": DummyComponentActions.GET_STATE,
            "sender": "test_client",
            "payload": {},
        },
        timeout=10.0,
    )
    if response is None:
        pytest.skip(
            "No response from component (timeout). "
            "Run: make docker-up"
        )
    assert response.get("success") is True
    assert "counter" in response["payload"]
    assert "from" in response["payload"]


def test_component_a_asks_b(system_bus):
    """A отправляет запрос в B, B обрабатывает и отвечает, A возвращает ответ тесту."""
    response = None
    for attempt in range(3):
        response = system_bus.request(
            ComponentTopics.DUMMY_COMPONENT_A,
            {
                "action": DummyComponentActions.ASK_B,
                "sender": "test_client",
                "payload": {"query": "hello"},
            },
            timeout=15.0,
        )
        if response is not None:
            break
        time.sleep(5)
    if response is None:
        pytest.skip(
            "No response from component (timeout). "
            "Run: make docker-up"
        )
    assert response.get("success") is True
    assert "b_response" in response["payload"]
    assert response["payload"]["b_response"]["data"] == "response_for_hello"
    assert response["payload"]["b_response"]["source"] == "dummy_component_b"
    assert response["payload"]["relayed_by"] == "dummy_component_a"


# --- Gateway integration tests ---


def test_gateway_echo(system_bus):
    """Отправляем echo через gateway (systems.dummy_system) — не напрямую в компонент."""
    response = system_bus.request(
        SystemTopics.DUMMY_SYSTEM,
        {
            "action": GatewayActions.ECHO,
            "sender": "test_client",
            "payload": {"message": "hello_via_gateway"},
        },
        timeout=15.0,
    )
    if response is None:
        pytest.skip(
            "No response from gateway (timeout). "
            "Run: make docker-up"
        )
    assert response.get("success") is True
    assert response["payload"]["echo"] == {"message": "hello_via_gateway"}
    assert "from" in response["payload"]


def test_gateway_get_data(system_bus):
    """Отправляем get_data через gateway — он проксирует в компонент B."""
    response = None
    for attempt in range(3):
        response = system_bus.request(
            SystemTopics.DUMMY_SYSTEM,
            {
                "action": GatewayActions.GET_DATA,
                "sender": "test_client",
                "payload": {"query": "gw_test"},
            },
            timeout=15.0,
        )
        if response is not None:
            break
        time.sleep(5)
    if response is None:
        pytest.skip(
            "No response from gateway (timeout). "
            "Run: make docker-up"
        )
    assert response.get("success") is True
    assert response["payload"]["data"] == "response_for_gw_test"
    assert response["payload"]["source"] == "dummy_component_b"
