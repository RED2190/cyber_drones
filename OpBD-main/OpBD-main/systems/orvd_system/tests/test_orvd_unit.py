import pytest
from unittest.mock import MagicMock

from systems.orvd_system.src.gateway.src.gateway import OrvdGateway
from components.orvd_component.src.orvd_component import OrvdComponent
from systems.orvd_system.src.gateway.topics import ComponentTopics, GatewayActions


# ==========================================================
# COMPONENT TESTS (через mock bus)
# ==========================================================

@pytest.fixture
def component_and_bus():
    mock_bus = MagicMock()

    component = OrvdComponent(
        component_id="orvd_component_1",
        name="ORVD",
        bus=mock_bus,
    )

    return component, mock_bus


def test_register_drone(component_and_bus):
    component, _ = component_and_bus

    message = {
        "action": GatewayActions.REGISTER_DRONE,
        "sender": "v1.Agrodron.Agrodron001.security_monitor",
        "payload": {"drone_id": "D1"},
    }

    result = component._handle_register_drone(message)

    assert result["status"] == "registered"
    assert result["drone_id"] == "D1"


def test_register_mission_without_drone(component_and_bus):
    component, _ = component_and_bus

    message = {
        "action": GatewayActions.REGISTER_MISSION,
        "sender": "external",
        "payload": {"mission_id": "M1", "drone_id": "D1"},
    }

    result = component._handle_register_mission(message)

    assert result["status"] == "error"


def test_authorize_and_takeoff_flow(component_and_bus):
    component, _ = component_and_bus

    # register drone
    component._handle_register_drone({
        "action": "register_drone",
        "sender": "external",
        "payload": {"drone_id": "D1"},
    })

    # register mission
    component._handle_register_mission({
        "action": "register_mission",
        "sender": "external",
        "payload": {
            "mission_id": "M1",
            "drone_id": "D1",
            "route": []
        },
    })

    # authorize mission
    component._handle_authorize_mission({
        "action": "authorize_mission",
        "sender": "external",
        "payload": {"mission_id": "M1"},
    })

    # request takeoff
    result = component._handle_request_takeoff({
        "action": "request_takeoff",
        "sender": "external",
        "payload": {"drone_id": "D1", "mission_id": "M1"},
    })

    assert result["status"] == "takeoff_authorized"

    # ==========================================================
# GATEWAY TESTS
# ==========================================================

@pytest.fixture
def gateway_and_bus():
    mock_bus = MagicMock()

    gw = OrvdGateway(
        system_id="orvd_gateway",
        bus=mock_bus,
    )

    return gw, mock_bus


def test_gateway_routes_register_drone(gateway_and_bus):
    gw, bus = gateway_and_bus

    bus.request.return_value = {
        "success": True,
        "payload": {
            "status": "registered",
            "drone_id": "D1",
        },
    }

    message = {
        "action": GatewayActions.REGISTER_DRONE,
        "sender": "v1.Agrodron.Agrodron001.security_monitor",
        "payload": {"drone_id": "D1"},
    }

    result = gw._handle_proxy(message)

    bus.request.assert_called_once_with(
        ComponentTopics.ORVD_COMPONENT,
        {
            "action": GatewayActions.REGISTER_DRONE,
            "sender": "orvd_gateway",
            "payload": {"drone_id": "D1"},
        },
        timeout=10.0,
    )

    assert result["status"] == "registered"


def test_gateway_timeout_returns_error(gateway_and_bus):
    gw, bus = gateway_and_bus
    bus.request.return_value = None

    message = {
        "action": GatewayActions.REGISTER_DRONE,
        "sender": "external",
        "payload": {"drone_id": "D1"},
    }

    result = gw._handle_proxy(message)

    assert "error" in result

# Полный сценарий

def test_full_mission_lifecycle(component_and_bus):
    component, _ = component_and_bus

    # --- REGISTER DRONE ---
    component._handle_register_drone({
        "action": "register_drone",
        "sender": "external",
        "payload": {"drone_id": "D1"},
    })

    assert "D1" in component._drones
    assert component._history[-1]["event"] == "drone_registered"

    # --- REGISTER MISSION ---
    component._handle_register_mission({
        "action": "register_mission",
        "sender": "external",
        "payload": {
            "mission_id": "M1",
            "drone_id": "D1",
            "route": []
        },
    })

    assert "M1" in component._missions
    assert component._history[-1]["event"] == "mission_registered"

    # --- AUTHORIZE ---
    component._handle_authorize_mission({
        "action": "authorize_mission",
        "sender": "external",
        "payload": {"mission_id": "M1"},
    })

    assert "M1" in component._authorized
    assert component._history[-1]["event"] == "mission_authorized"

    # --- TAKEOFF ---
    component._handle_request_takeoff({
        "action": "request_takeoff",
        "sender": "external",
        "payload": {"drone_id": "D1", "mission_id": "M1"},
    })

    assert component._active_flights["D1"] == "M1"
    assert component._history[-1]["event"] == "takeoff_authorized"

# Осмотрим payload

def test_gateway_inspect_payload(gateway_and_bus):
    gw, bus = gateway_and_bus

    bus.request.return_value = {
        "success": True,
        "payload": {"status": "registered"}
    }

    message = {
        "action": GatewayActions.REGISTER_DRONE,
        "sender": "external",
        "payload": {"drone_id": "D1"},
    }

    gw._handle_proxy(message)

    # Получаем реальные аргументы вызова
    called_args = bus.request.call_args

    topic = called_args[0][0]
    payload = called_args[0][1]
    timeout = called_args[1]["timeout"]

    print("Topic:", topic)
    print("Payload:", payload)
    print("Timeout:", timeout)

    assert topic == ComponentTopics.ORVD_COMPONENT
    assert payload["sender"] == "orvd_gateway"
    assert payload["action"] == "register_drone"
    assert timeout == 10.0

# подписка

def test_component_start_subscribes(component_and_bus):
    component, bus = component_and_bus

    component.start()

    bus.subscribe.assert_called()

# логи истории

def test_history_records_events(component_and_bus):
    component, _ = component_and_bus

    component._handle_register_drone({
        "action": "register_drone",
        "sender": "external",
        "payload": {"drone_id": "D1"},
    })

    history = component._history

    assert len(history) == 1
    assert history[0]["event"] == "drone_registered"
    assert history[0]["drone_id"] == "D1"