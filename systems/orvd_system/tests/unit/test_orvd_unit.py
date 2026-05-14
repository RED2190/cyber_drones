import pytest
from unittest.mock import MagicMock

from src.gateway.src.gateway import OrvdGateway
from src.orvd_component import OrvdComponent
from src.gateway.topics import ComponentTopics, GatewayActions


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

# register_drone (ошибки + сертификат)

def test_register_drone_without_id(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_register_drone({"payload": {}})

    assert result["status"] == "error"


def test_register_drone_with_invalid_cert(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_register_drone({
        "payload": {"drone_id": "D1", "certificate_id": "bad_cert"}
    })

    assert result["status"] == "error"
    assert "invalid certificate" in result.get("message", "")


def test_register_drone_with_valid_cert(component_and_bus):
    component, bus = component_and_bus

    bus.request.return_value = {"success": True, "payload": {"valid": True}}

    result = component._handle_register_drone({
        "payload": {"drone_id": "D1", "certificate_id": "good_cert"}
    })

    assert result["status"] == "registered"

# mission + зоны

def test_mission_rejected_by_zone(component_and_bus):
    component, _ = component_and_bus

    component._no_fly_zones["Z1"] = {
        "active": True,
        "bounds": {"min_lat": 0, "max_lat": 100, "min_lon": 0, "max_lon": 100}
    }

    component._handle_register_drone({"payload": {"drone_id": "D1"}})

    result = component._handle_register_mission({
        "payload": {
            "mission_id": "M1",
            "drone_id": "D1",
            "route": [{"lat": 50, "lon": 50}]
        }
    })

    assert result["status"] == "rejected"

# authorize_mission

def test_authorize_missing_mission(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_authorize_mission({
        "payload": {"mission_id": "UNKNOWN"}
    })

    assert result["status"] == "error"

# request_takeoff

def test_takeoff_no_mission_id(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_request_takeoff({"payload": {}})
    assert result["status"] == "error"


def test_takeoff_mission_not_found(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_request_takeoff({
        "payload": {"mission_id": "M1"}
    })

    assert result["status"] == "takeoff_denied"


def test_takeoff_not_authorized(component_and_bus):
    component, _ = component_and_bus

    component._missions["M1"] = {"drone_id": "D1"}

    result = component._handle_request_takeoff({
        "payload": {"mission_id": "M1"}
    })

    assert result["status"] == "takeoff_denied"


def test_takeoff_drone_not_registered(component_and_bus):
    component, _ = component_and_bus

    component._missions["M1"] = {"drone_id": "D1"}
    component._authorized.add("M1")

    result = component._handle_request_takeoff({
        "payload": {"mission_id": "M1"}
    })

    assert result["status"] == "takeoff_denied"


def test_takeoff_already_flying(component_and_bus):
    component, _ = component_and_bus

    component._drones["D1"] = {}
    component._missions["M1"] = {"drone_id": "D1"}
    component._authorized.add("M1")
    component._active_flights["D1"] = "M1"

    result = component._handle_request_takeoff({
        "payload": {"mission_id": "M1"}
    })

    assert result["status"] == "takeoff_denied"

# revoke_takeoff

def test_revoke_not_active(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_revoke_takeoff({
        "payload": {"drone_id": "D1"}
    })

    assert result["status"] == "error"

# telemetry

def test_telemetry_without_drone_id(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_send_telemetry({"payload": {}})
    assert result["status"] == "error"


def test_telemetry_zone_violation(component_and_bus):
    component, _ = component_and_bus

    component._no_fly_zones["Z1"] = {
        "active": True,
        "bounds": {"min_lat": 0, "max_lat": 100, "min_lon": 0, "max_lon": 100}
    }

    result = component._handle_send_telemetry({
        "payload": {
            "drone_id": "D1",
            "coords": {"lat": 50, "lon": 50}
        }
    })

    assert result["status"] == "emergency"

# request_telemetry

def test_request_telemetry_timeout(component_and_bus):
    component, bus = component_and_bus

    bus.request.side_effect = Exception()

    result = component._handle_request_telemetry({
        "payload": {"drone_id": "D1", "drone_topic": "test"}
    })

    assert result["status"] == "error"


def test_request_telemetry_ok(component_and_bus):
    component, bus = component_and_bus

    bus.request.return_value = {
        "payload": {"lat": 1, "lon": 1}
    }

    result = component._handle_request_telemetry({
        "payload": {"drone_id": "D1", "drone_topic": "test"}
    })

    assert result["status"] == "telemetry_ok"

# Зоны

def test_add_zone_without_id(component_and_bus):
    component, _ = component_and_bus

    result = component._handle_add_zone({"payload": {}})
    assert result["status"] == "error"


def test_remove_zone(component_and_bus):
    component, _ = component_and_bus

    component._no_fly_zones["Z1"] = {}

    result = component._handle_remove_zone({
        "payload": {"zone_id": "Z1"}
    })

    assert result["status"] == "zone_removed"

def test_point_not_in_zone(component_and_bus):
    component, _ = component_and_bus

    result = component._point_in_no_fly_zone({"lat": 10, "lon": 10})

    assert result is False


def test_route_violation(component_and_bus):
    component, _ = component_and_bus

    component._no_fly_zones["Z1"] = {
        "active": True,
        "bounds": {"min_lat": 0, "max_lat": 100, "min_lon": 0, "max_lon": 100}
    }

    result = component._route_violates_zone([{"lat": 50, "lon": 50}])

    assert result is True

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