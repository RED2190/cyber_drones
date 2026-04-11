"""
E2E тесты DronePort через реальный брокер и поднятые docker-контейнеры.
Требуют: make docker-up и make drone-port-system-up.
Если брокер или компоненты недоступны, тесты пропускаются.
"""
import os
import socket
import time
import uuid

import pytest

from systems.drone_port.src.charging_manager.topics import ComponentTopics as ChargingTopics, ChargingManagerActions
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions
from systems.drone_port.src.orchestrator.topics import ComponentTopics as OrchestratorTopics, OrchestratorActions
from systems.drone_port.src.state_store.topics import ComponentTopics as StateStoreTopics, StateStoreActions


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
            f"Broker at {os.environ.get('BROKER_HOST', 'localhost')} not available. "
            "Run: make docker-up"
        )
    _ensure_broker_env()
    from broker.src.bus_factory import create_system_bus

    bus = create_system_bus(client_id=f"drone_port_test_{uuid.uuid4().hex[:8]}")
    bus.start()
    time.sleep(2)
    yield bus
    bus.stop()


def test_state_store_returns_seeded_ports(system_bus):
    response = system_bus.request(
        StateStoreTopics.STATE_STORE,
        {
            "action": StateStoreActions.GET_ALL_PORTS,
            "sender": "test_client",
            "payload": {},
        },
        timeout=10.0,
    )
    if response is None:
        pytest.skip("No response from state_store. Run: make drone-port-system-up")

    assert response.get("success") is True
    assert len(response["payload"]["ports"]) >= 4
    assert {"lat", "lon"} <= set(response["payload"]["ports"][0].keys())


def test_charging_flow_updates_registry_and_orchestrator_responds(system_bus):
    drone_id = f"DR-CHARGE-{uuid.uuid4().hex[:6]}"
    system_bus.publish(
        RegistryTopics.DRONE_REGISTRY,
        {
            "action": DroneRegistryActions.REGISTER_DRONE,
            "sender": "test_client",
            "payload": {"drone_id": drone_id, "model": "TestModel"},
        },
    )
    time.sleep(1)

    system_bus.publish(
        ChargingTopics.CHARGING_MANAGER,
        {
            "action": ChargingManagerActions.START_CHARGING,
            "sender": "test_client",
            "payload": {"drone_id": drone_id, "battery": 95.0},
        },
    )

    registry_response = None
    for _ in range(15):
        registry_response = system_bus.request(
            RegistryTopics.DRONE_REGISTRY,
            {
                "action": DroneRegistryActions.GET_DRONE,
                "sender": "test_client",
                "payload": {"drone_id": drone_id},
            },
            timeout=5.0,
        )
        if registry_response and registry_response.get("success") and registry_response["payload"].get("battery") == 100.0:
            break
        time.sleep(1)

    if registry_response is None:
        pytest.skip("No response from drone_registry. Run: make drone-port-system-up")

    assert registry_response.get("success") is True
    assert registry_response["payload"]["status"] == "ready"
    assert float(registry_response["payload"]["battery"]) == 100.0

    available_response = system_bus.request(
        RegistryTopics.DRONE_REGISTRY,
        {
            "action": DroneRegistryActions.GET_AVAILABLE_DRONES,
            "sender": "test_client",
            "payload": {},
        },
        timeout=10.0,
    )
    assert available_response is not None
    assert available_response.get("success") is True
    assert any(
        drone["drone_id"] == drone_id
        for drone in available_response["payload"]["drones"]
    )

    orchestrator_response = system_bus.request(
        OrchestratorTopics.ORCHESTRATOR,
        {
            "action": OrchestratorActions.GET_AVAILABLE_DRONES,
            "sender": "test_client",
            "payload": {},
        },
        timeout=10.0,
    )
    if orchestrator_response is None:
        pytest.skip("No response from orchestrator. Run: make drone-port-system-up")

    assert orchestrator_response.get("success") is True
    assert "from" in orchestrator_response["payload"]
