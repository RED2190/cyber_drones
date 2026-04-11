"""
E2E тесты ORVD системы через реальный брокер.
Требует: make docker-up (Kafka/Mosquitto + ORVD gateway + ORVD component).
Если контейнеры не запущены — тесты пропускаются (skip).
"""

import pytest
import os
import time
import socket

from systems.orvd_system.src.gateway.topics import SystemTopics, GatewayActions
from systems.orvd_system.src.orvd_component.topics import ComponentTopics


def _broker_available(retries=5, delay=2):
    """Проверяем доступность брокера (Kafka/MQTT) перед запуском E2E."""
    bt = os.environ.get("BROKER_TYPE", "kafka").lower().strip().split("#")[0].strip()
    host = os.environ.get("BROKER_HOST", "localhost")
    port_val = (
        os.environ.get("MQTT_PORT", "1883") if bt == "mqtt" else os.environ.get("KAFKA_PORT", "9092")
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

    bus = create_system_bus(client_id="test_client")
    bus.start()
    time.sleep(15)
    yield bus
    bus.stop()


# ==========================================================
# COMPONENT TESTS
# ==========================================================

def test_register_drone_and_mission(system_bus):
    """Регистрация дрона и миссии через gateway + компонент."""
    drone_msg = {
        "action": GatewayActions.REGISTER_DRONE,
        "sender": SystemTopics.ORVD_SYSTEM,
        "payload": {"drone_id": "DRONE_1"},
    }
    resp_drone = system_bus.request(ComponentTopics.ORVD_COMPONENT, drone_msg, timeout=10.0)
    print("Register drone response:", resp_drone)
    assert resp_drone["status"] == "registered"

    mission_msg = {
        "action": GatewayActions.REGISTER_MISSION,
        "sender": SystemTopics.ORVD_SYSTEM,
        "payload": {
            "mission_id": "MISSION_1",
            "drone_id": "DRONE_1",
            "route": [{"lat": 60.0, "lon": 30.0}],
        },
    }
    resp_mission = system_bus.request(ComponentTopics.ORVD_COMPONENT, mission_msg, timeout=10.0)
    print("Register mission response:", resp_mission)
    assert resp_mission["status"] == "mission_registered"


def test_authorize_and_takeoff(system_bus):
    """Авторизация миссии и запрос на взлет."""
    # authorize mission
    auth_msg = {
        "action": GatewayActions.AUTHORIZE_MISSION,
        "sender": SystemTopics.ORVD_SYSTEM,
        "payload": {"mission_id": "MISSION_1"},
    }
    resp_auth = system_bus.request(ComponentTopics.ORVD_COMPONENT, auth_msg, timeout=10.0)
    print("Authorize mission response:", resp_auth)
    assert resp_auth["status"] == "authorized"

    # request takeoff
    takeoff_msg = {
        "action": GatewayActions.REQUEST_TAKEOFF,
        "sender": SystemTopics.ORVD_SYSTEM,
        "payload": {"drone_id": "DRONE_1", "mission_id": "MISSION_1"},
    }
    resp_takeoff = system_bus.request(ComponentTopics.ORVD_COMPONENT, takeoff_msg, timeout=10.0)
    print("Request takeoff response:", resp_takeoff)
    assert resp_takeoff["status"] == "takeoff_authorized"


def test_get_history(system_bus):
    """Проверяем историю событий компонента."""
    history_msg = {
        "action": GatewayActions.GET_HISTORY,
        "sender": SystemTopics.ORVD_SYSTEM,
        "payload": {},
    }
    resp_history = system_bus.request(ComponentTopics.ORVD_COMPONENT, history_msg, timeout=10.0)
    print("Component history:", resp_history)
    assert "history" in resp_history
    # убеждаемся, что есть события регистрации дрона и миссии
    events = [e["event"] for e in resp_history["history"]]
    assert "drone_registered" in events
    assert "mission_registered" in events
    assert "mission_authorized" in events
    assert "takeoff_authorized" in events


# ==========================================================
# Gateway integration test
# ==========================================================

def test_gateway_register_drone(system_bus):
    """Отправка REGISTER_DRONE через gateway."""
    msg = {
        "action": GatewayActions.REGISTER_DRONE,
        "sender": "test_client",
        "payload": {"drone_id": "DRONE_2"},
    }
    resp = system_bus.request(SystemTopics.ORVD_SYSTEM, msg, timeout=10.0)
    print("Gateway register drone response:", resp)
    assert resp["status"] == "registered"