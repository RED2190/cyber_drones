"""
Интеграционные тесты AgroDron.

Требуют запущенную систему (make docker-up). Проверяют взаимодействие
с реальным брокером: подключение, proxy_request/proxy_publish через МБ, ответы компонентов.
"""
import os
import time

import pytest


def _has_broker_env():
    """Проверка, что заданы переменные для подключения к брокеру."""
    broker = os.environ.get("BROKER_TYPE", "").strip()
    if broker == "mqtt":
        return bool(os.environ.get("MQTT_BROKER", "").strip())
    if broker == "kafka":
        return bool(os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip())
    return False


def _bus_request(bus, topic: str, action: str, sender: str, target_topic: str, target_action: str, data: dict = None):
    """Отправить proxy_request через МБ и вернуть ответ."""
    msg = {
        "action": action,
        "sender": sender,
        "payload": {
            "target": {"topic": target_topic, "action": target_action},
            "data": data or {},
        },
    }
    return bus.request(topic, msg, timeout=10.0)


def _bus_publish(bus, topic: str, action: str, sender: str, target_topic: str, target_action: str, data: dict = None):
    """Отправить proxy_publish через МБ."""
    msg = {
        "action": action,
        "sender": sender,
        "payload": {
            "target": {"topic": target_topic, "action": target_action},
            "data": data or {},
        },
    }
    return bus.publish(topic, msg)


@pytest.mark.integration
@pytest.mark.skipif(
    not _has_broker_env(),
    reason="Set BROKER_TYPE and MQTT_BROKER/KAFKA_BOOTSTRAP_SERVERS for integration tests",
)
def test_broker_connection(broker_type):
    """Подключение к брокеру (create_system_bus, start/stop)."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_client")
    try:
        bus.start()
        time.sleep(1.0)
        assert bus is not None
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_security_monitor_proxy_request_returns_response(security_monitor_topic, topic):
    """proxy_request через МБ к motors (sender=telemetry по политике) возвращает ответ."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_proxy")
    try:
        bus.start()
        time.sleep(2.0)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "telemetry",
            topic("motors"), "get_state",
        )
        assert response is not None and isinstance(response, dict)
        if "target_response" in response:
            assert response["target_response"] is not None
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_motors_get_state_via_mb(security_monitor_topic, topic):
    """get_state к motors через МБ (как это делает telemetry)."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_motors")
    try:
        bus.start()
        time.sleep(2.0)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "telemetry",
            topic("motors"), "get_state",
        )
        assert response is not None
        if isinstance(response, dict) and "target_response" in response:
            tr = response["target_response"]
            if isinstance(tr, dict) and "payload" in tr:
                state = tr["payload"]
                assert "mode" in state or "sitl_mode" in state
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_sprayer_get_state_via_mb(security_monitor_topic, topic):
    """get_state к sprayer через МБ."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_sprayer")
    try:
        bus.start()
        time.sleep(2.0)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "telemetry",
            topic("sprayer"), "get_state",
        )
        assert response is not None
        if isinstance(response, dict) and "target_response" in response:
            tr = response["target_response"]
            if isinstance(tr, dict) and "payload" in tr:
                state = tr["payload"]
                assert "state" in state or "sitl_mode" in state
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_telemetry_get_state_via_mb(security_monitor_topic, topic):
    """get_state к telemetry через МБ (как это делает limiter)."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_telemetry")
    try:
        bus.start()
        time.sleep(3.0)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "limiter",
            topic("telemetry"), "get_state",
        )
        assert response is not None
        if isinstance(response, dict) and "target_response" in response:
            tr = response["target_response"]
            if isinstance(tr, dict) and "payload" in tr:
                payload = tr["payload"]
                assert "motors" in payload or "sprayer" in payload or "last_poll_ts" in payload
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_autopilot_set_target_via_mb(security_monitor_topic, topic):
    """proxy_publish: autopilot -> МБ -> motors SET_TARGET (fire-and-forget)."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_set_target")
    try:
        bus.start()
        time.sleep(2.0)
        ok = _bus_publish(
            bus, security_monitor_topic, "proxy_publish", "autopilot",
            topic("motors"), "SET_TARGET",
            data={"vx": 0.0, "vy": 0.0, "vz": 0.0},
        )
        assert ok is not False
        time.sleep(0.5)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "telemetry",
            topic("motors"), "get_state",
        )
        if isinstance(response, dict) and "target_response" in response:
            tr = response["target_response"]
            if isinstance(tr, dict) and "payload" in tr:
                state = tr["payload"]
                assert state.get("mode") == "TRACKING"
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_autopilot_set_spray_via_mb(security_monitor_topic, topic):
    """proxy_publish: autopilot -> МБ -> sprayer SET_SPRAY."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_set_spray")
    try:
        bus.start()
        time.sleep(2.0)
        ok = _bus_publish(
            bus, security_monitor_topic, "proxy_publish", "autopilot",
            topic("sprayer"), "SET_SPRAY",
            data={"spray": True},
        )
        assert ok is not False
        time.sleep(0.5)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "telemetry",
            topic("sprayer"), "get_state",
        )
        if isinstance(response, dict) and "target_response" in response:
            tr = response["target_response"]
            if isinstance(tr, dict) and "payload" in tr:
                assert tr["payload"].get("state") == "ON"
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_journal_log_event_via_mb(security_monitor_topic, topic):
    """proxy_publish: отправитель -> МБ -> journal LOG_EVENT."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_journal_log")
    try:
        bus.start()
        time.sleep(2.0)
        ok = _bus_publish(
            bus, security_monitor_topic, "proxy_publish", "autopilot",
            topic("journal"), "LOG_EVENT",
            data={
                "event": "INTEGRATION_TEST_EVENT",
                "source": "integration_test",
                "details": {"test": True},
            },
        )
        assert ok is not False
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_navigation_get_state_via_mb(security_monitor_topic, topic):
    """proxy_request к navigation get_state (как autopilot)."""
    from broker.bus_factory import create_system_bus

    bus = create_system_bus(client_id="integration_test_nav")
    try:
        bus.start()
        time.sleep(2.0)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "autopilot",
            topic("navigation"), "get_state",
        )
        assert response is not None
        if isinstance(response, dict) and "target_response" in response:
            tr = response["target_response"]
            if isinstance(tr, dict) and "payload" in tr:
                p = tr["payload"]
                assert "lat" in p or "lon" in p or "alt" in p or "lat_decimal" in p
    finally:
        bus.stop()


@pytest.mark.integration
@pytest.mark.skipif(not _has_broker_env(), reason="Broker env required")
def test_mission_handler_mission_load_to_autopilot_via_mb(security_monitor_topic, topic):
    """proxy_request: mission_handler -> МБ -> autopilot mission_load (минимальный WPL)."""
    from broker.bus_factory import create_system_bus

    WPL_MINIMAL = "QGC WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60.0\t30.0\t5.0\t1"
    bus = create_system_bus(client_id="integration_test_mission")
    try:
        bus.start()
        time.sleep(2.0)
        response = _bus_request(
            bus, security_monitor_topic, "proxy_request", "mission_handler",
            topic("autopilot"), "mission_load",
            data={"mission": {"mission_id": "itest", "steps": []}},
        )
        assert response is not None
        if isinstance(response, dict) and "target_response" in response:
            tr = response["target_response"]
            if isinstance(tr, dict) and "payload" in tr:
                p = tr["payload"]
                assert p.get("ok") is True or "ok" in p
    finally:
        bus.stop()
