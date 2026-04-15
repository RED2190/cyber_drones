"""Unit тесты OrvdComponent (без брокера, через моки)."""

import pytest
from unittest.mock import MagicMock

from orvd_component.src.orvd_component import OrvdComponent


@pytest.fixture
def bus():
    return MagicMock()

@pytest.fixture
def bus():
    bus = MagicMock()

    # имитируем ответ дрона
    bus.request.return_value = {
        "payload": {
            "lat": 60.0,
            "lon": 30.0,
            "alt_m": 5.0,
            "gps_valid": True
        }
    }

    return bus

@pytest.fixture
def component(bus):
    return OrvdComponent(
        component_id="orvd_test",
        name="TestORVD",
        bus=bus,
    )


# ---------------------------------------------------------
# START / SUBSCRIBE
# ---------------------------------------------------------

def test_subscribe_on_start(component, bus):
    component.start()
    print("[DEBUG] Component started and should subscribe to bus")
    bus.subscribe.assert_called()


# ---------------------------------------------------------
# DRONE REGISTRATION
# ---------------------------------------------------------

def test_register_drone(component):
    msg = {
        "action": "register_drone",
        "payload": {"drone_id": "drone_1"}
    }

    result = component._handle_register_drone(msg)
    print(f"[DEBUG] Register drone result: {result}")
    assert result["status"] == "registered"
    assert "drone_1" in component._drones


# ---------------------------------------------------------
# NO-FLY ZONE
# ---------------------------------------------------------

def test_add_no_fly_zone(component):
    msg = {
        "payload": {
            "zone_id": "zone_1",
            "active": True,
            "bounds": {
                "min_lat": 10,
                "max_lat": 20,
                "min_lon": 10,
                "max_lon": 20,
            }
        }
    }

    result = component._handle_add_zone(msg)
    print(f"[DEBUG] Add zone result: {result}")
    assert result["status"] == "zone_added"
    assert "zone_1" in component._no_fly_zones


# ---------------------------------------------------------
# MISSION REJECTED (ROUTE INSIDE ZONE)
# ---------------------------------------------------------

def test_register_mission_rejected_due_to_zone(component):
    component._drones["drone_1"] = {}

    component._no_fly_zones["zone_1"] = {
        "active": True,
        "bounds": {
            "min_lat": 10,
            "max_lat": 20,
            "min_lon": 10,
            "max_lon": 20,
        }
    }

    msg = {
        "payload": {
            "mission_id": "m1",
            "drone_id": "drone_1",
            "route": [{"lat": 15, "lon": 15}]
        }
    }

    result = component._handle_register_mission(msg)
    print(f"[DEBUG] Mission rejected result: {result}")
    assert result["status"] == "rejected"


# ---------------------------------------------------------
# MISSION SUCCESS FLOW
# ---------------------------------------------------------

def test_full_mission_flow(component):

    # 1. Register drone
    component._handle_register_drone({
        "payload": {"drone_id": "drone_1"}
    })
    print("[DEBUG] Drone registered for mission flow")

    # 2. Register mission (valid route)
    mission_msg = {
        "payload": {
            "mission_id": "m1",
            "drone_id": "drone_1",
            "route": [{"lat": 50, "lon": 50}]
        }
    }

    result = component._handle_register_mission(mission_msg)
    print(f"[DEBUG] Mission registered result: {result}")
    assert result["status"] == "mission_registered"

    # 3. Authorize mission
    auth_result = component._handle_authorize_mission({
        "payload": {"mission_id": "m1"}
    })
    print(f"[DEBUG] Mission authorized result: {auth_result}")
    assert auth_result["status"] == "authorized"

    # 4. Request takeoff
    takeoff_result = component._handle_request_takeoff({
        "payload": {
            "drone_id": "drone_1",
            "mission_id": "m1"
        }
    })
    print(f"[DEBUG] Takeoff result: {takeoff_result}")
    assert takeoff_result["status"] == "takeoff_authorized"
    assert "drone_1" in component._active_flights


# ---------------------------------------------------------
# TELEMETRY EMERGENCY
# ---------------------------------------------------------

def test_telemetry_zone_violation(component):

    component._drones["drone_1"] = {}

    component._no_fly_zones["zone_1"] = {
        "active": True,
        "bounds": {
            "min_lat": 10,
            "max_lat": 20,
            "min_lon": 10,
            "max_lon": 20,
        }
    }

    msg = {
        "payload": {
            "drone_id": "drone_1",
            "coords": {"lat": 15, "lon": 15}
        }
    }

    result = component._handle_send_telemetry(msg)
    print(f"[DEBUG] Telemetry emergency result: {result}")
    assert result["status"] == "emergency"
    assert result["command"] == "LAND"


def test_request_telemetry_ok(component):
    message = {
        "action": "request_telemetry",
        "payload": {
            "drone_id": "drone_1",
            "drone_topic": "v1.Agrodron.Agrodron001.navigation"
        }
    }

    result = component._handle_request_telemetry(message)

    assert result["status"] == "telemetry_ok"


# ---------------------------------------------------------
# REVOKE TAKEOFF
# ---------------------------------------------------------

def test_revoke_takeoff(component):

    component._drones["drone_1"] = {}
    component._authorized.add("m1")
    component._active_flights["drone_1"] = "m1"

    result = component._handle_revoke_takeoff({
        "payload": {"drone_id": "drone_1"}
    })
    print(f"[DEBUG] Revoke takeoff result: {result}")
    assert result["status"] == "landing_required"
    assert "drone_1" not in component._active_flights


# ---------------------------------------------------------
# HISTORY
# ---------------------------------------------------------

def test_history(component):

    component._handle_register_drone({
        "payload": {"drone_id": "drone_1"}
    })

    result = component._handle_get_history({"payload": {}})
    print(f"[DEBUG] History result count: {len(result['history'])}")
    assert len(result["history"]) > 0