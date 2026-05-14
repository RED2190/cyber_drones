"""
SAFE integration tests for ORVD system.

НЕ ТРЕБУЮТ:
- docker
- kafka
- mqtt
- реальные брокеры

Цель:
- проверить интеграцию OrvdComponent + message handlers
- через mocked SystemBus
"""

import pytest
from unittest.mock import MagicMock

from src.orvd_component import OrvdComponent


# ==========================================================
# FIXTURE: fake bus
# ==========================================================

@pytest.fixture
def fake_bus():
    bus = MagicMock()
    bus.request.return_value = {
        "success": True,
        "payload": {"valid": True}
    }
    return bus


@pytest.fixture
def component(fake_bus):
    return OrvdComponent(
        component_id="orvd",
        name="ORVD",
        bus=fake_bus,
    )


# ==========================================================
# DRONE FLOW
# ==========================================================

def test_register_drone(component):
    result = component._handle_register_drone({
        "payload": {"drone_id": "D1"}
    })

    assert result["status"] == "registered"
    assert "D1" in component._drones


def test_register_drone_invalid(component):
    # без drone_id
    result = component._handle_register_drone({
        "payload": {}
    })

    assert result["status"] == "error"


# ==========================================================
# MISSION FLOW
# ==========================================================

def test_register_mission(component):
    component._drones["D1"] = {"drone_id": "D1"}

    result = component._handle_register_mission({
        "payload": {
            "mission_id": "M1",
            "drone_id": "D1",
            "route": []
        }
    })

    assert result["status"] == "mission_registered"
    assert "M1" in component._missions


def test_register_mission_unknown_drone(component):
    result = component._handle_register_mission({
        "payload": {
            "mission_id": "M1",
            "drone_id": "UNKNOWN",
            "route": []
        }
    })

    assert result["status"] == "error"


# ==========================================================
# AUTH + TAKEOFF
# ==========================================================

def test_authorize_and_takeoff(component):
    component._drones["D1"] = {"drone_id": "D1"}
    component._missions["M1"] = {"mission_id": "M1", "drone_id": "D1"}

    auth = component._handle_authorize_mission({
        "payload": {"mission_id": "M1"}
    })

    assert auth["status"] == "authorized"

    takeoff = component._handle_request_takeoff({
        "payload": {"mission_id": "M1"}
    })

    assert takeoff["status"] == "takeoff_authorized"


def test_takeoff_without_auth(component):
    component._drones["D1"] = {"drone_id": "D1"}
    component._missions["M1"] = {"mission_id": "M1", "drone_id": "D1"}

    resp = component._handle_request_takeoff({
        "payload": {"mission_id": "M1"}
    })

    assert resp["status"] == "takeoff_denied"


# ==========================================================
# TELEMETRY + ZONE
# ==========================================================

def test_no_fly_zone_violation(component):
    component._no_fly_zones["Z1"] = {
        "active": True,
        "bounds": {
            "min_lat": 0,
            "max_lat": 10,
            "min_lon": 0,
            "max_lon": 10
        }
    }

    resp = component._handle_send_telemetry({
        "payload": {
            "drone_id": "D1",
            "coords": {"lat": 5, "lon": 5}
        }
    })

    assert resp["status"] == "emergency"
    assert resp["command"] == "LAND"


# ==========================================================
# HISTORY
# ==========================================================

def test_history(component):
    component._log("test_event", drone_id="D1")

    resp = component._handle_get_history({})

    assert "history" in resp
    assert any(e["event"] == "test_event" for e in resp["history"])