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
from systems.drone_port.src.drone_manager.topics import ComponentTopics as DroneManagerTopics, DroneManagerActions
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions
from systems.drone_port.src.port_manager.topics import ComponentTopics as PortTopics, PortManagerActions
from systems.drone_port.src.state_store.topics import ComponentTopics as StateStoreTopics, StateStoreActions
from systems.drone_port.topics import GatewayActions, SystemTopics


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

    gateway_response = system_bus.request(
        SystemTopics.DRONE_PORT,
        {
            "action": GatewayActions.GET_AVAILABLE_DRONES,
            "sender": "test_client",
            "payload": {},
        },
        timeout=10.0,
    )
    if gateway_response is None:
        pytest.skip("No response from gateway. Run: make drone-port-system-up")

    assert gateway_response.get("success") is True
    assert "drones" in gateway_response["payload"]


def test_new_drone_landing_and_takeoff_flow(system_bus):
    drone_id = f"DR-INTEGRATION-{uuid.uuid4().hex[:6]}"
    assigned_port_id = None

    ports_response = system_bus.request(
        StateStoreTopics.STATE_STORE,
        {
            "action": StateStoreActions.GET_ALL_PORTS,
            "sender": "integration_test",
            "payload": {},
        },
        timeout=10.0,
    )
    if ports_response is None:
        pytest.skip("No response from state_store. Run: make drone-port-system-up")
    assert ports_response.get("success") is True
    if not any(not port.get("drone_id") for port in ports_response["payload"]["ports"]):
        pytest.skip("No free ports available for landing/takeoff integration test")

    try:
        landing_response = system_bus.request(
            DroneManagerTopics.DRONE_MANAGER,
            {
                "action": DroneManagerActions.REQUEST_LANDING,
                "sender": "integration_test",
                "payload": {
                    "drone_id": drone_id,
                    "model": "IntegrationModel",
                    "battery": 100,
                },
            },
            timeout=10.0,
        )
        if landing_response is None:
            pytest.skip("No response from drone_manager. Run: make drone-port-system-up")
        assert landing_response.get("success") is True

        landing_payload = landing_response["payload"]
        assert landing_payload["approved"] is True
        assert landing_payload["drone_id"] == drone_id
        assigned_port_id = landing_payload["port_id"]

        reserved_port = None
        registered_drone = None
        for _ in range(10):
            ports_after_landing = system_bus.request(
                StateStoreTopics.STATE_STORE,
                {
                    "action": StateStoreActions.GET_ALL_PORTS,
                    "sender": "integration_test",
                    "payload": {},
                },
                timeout=10.0,
            )
            registry_response = system_bus.request(
                RegistryTopics.DRONE_REGISTRY,
                {
                    "action": DroneRegistryActions.GET_DRONE,
                    "sender": "integration_test",
                    "payload": {"drone_id": drone_id},
                },
                timeout=10.0,
            )
            if ports_after_landing and registry_response:
                ports = ports_after_landing["payload"]["ports"]
                reserved_port = next(
                    (port for port in ports if port["port_id"] == assigned_port_id),
                    None,
                )
                registered_drone = registry_response["payload"]
                if (
                    reserved_port
                    and reserved_port["drone_id"] == drone_id
                    and registered_drone.get("success") is True
                    and float(registered_drone.get("battery", -1)) == 100.0
                ):
                    break
            time.sleep(1)

        assert reserved_port is not None
        assert reserved_port["drone_id"] == drone_id
        assert reserved_port["status"] == "reserved"
        assert registered_drone["success"] is True
        assert registered_drone["model"] == "IntegrationModel"
        assert registered_drone["port_id"] == assigned_port_id
        assert float(registered_drone["battery"]) == 100.0
        assert registered_drone["status"] == "ready"

        takeoff_response = system_bus.request(
            DroneManagerTopics.DRONE_MANAGER,
            {
                "action": DroneManagerActions.REQUEST_TAKEOFF,
                "sender": "integration_test",
                "payload": {"drone_id": drone_id},
            },
            timeout=10.0,
        )
        assert takeoff_response is not None
        assert takeoff_response.get("success") is True

        takeoff_payload = takeoff_response["payload"]
        assert takeoff_payload["approved"] is True
        assert takeoff_payload["battery"] == 100.0
        assert takeoff_payload["port_id"] == assigned_port_id
        assert takeoff_payload["drone_id"] == drone_id
        assert takeoff_payload["port_coordinates"] == {
            "lat": reserved_port["lat"],
            "lon": reserved_port["lon"],
        }

        freed_port = None
        for _ in range(10):
            ports_after_takeoff = system_bus.request(
                StateStoreTopics.STATE_STORE,
                {
                    "action": StateStoreActions.GET_ALL_PORTS,
                    "sender": "integration_test",
                    "payload": {},
                },
                timeout=10.0,
            )
            if ports_after_takeoff:
                freed_port = next(
                    (
                        port
                        for port in ports_after_takeoff["payload"]["ports"]
                        if port["port_id"] == assigned_port_id
                    ),
                    None,
                )
                if freed_port and freed_port["drone_id"] == "" and freed_port["status"] == "free":
                    break
            time.sleep(1)

        assert freed_port is not None
        assert freed_port["drone_id"] == ""
        assert freed_port["status"] == "free"
    finally:
        if assigned_port_id:
            system_bus.publish(
                PortTopics.PORT_MANAGER,
                {
                    "action": PortManagerActions.FREE_SLOT,
                    "sender": "integration_test_cleanup",
                    "payload": {
                        "drone_id": drone_id,
                        "port_id": assigned_port_id,
                    },
                },
            )
        system_bus.publish(
            RegistryTopics.DRONE_REGISTRY,
            {
                "action": DroneRegistryActions.DELETE_DRONE,
                "sender": "integration_test_cleanup",
                "payload": {"drone_id": drone_id},
            },
        )
