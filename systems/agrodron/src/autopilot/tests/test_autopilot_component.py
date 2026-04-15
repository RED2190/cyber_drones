import os

from systems.agrodron.src.bus_mock import MockSystemBus
from systems.agrodron.src.autopilot.src.autopilot import AutopilotComponent
from systems.agrodron.src.autopilot import config

SM_TOPIC = config.security_monitor_topic()


def _make_component() -> AutopilotComponent:
    bus = MockSystemBus()
    return AutopilotComponent(component_id="autopilot_test", bus=bus)


def test_mission_load_and_start():
    saved = {k: os.environ.pop(k, None) for k in (
        "ORVD_TOPIC",
        "DRONEPORT_TOPIC",
        "AUTOPILOT_ORVD_MOCK_SUCCESS",
        "AUTOPILOT_DRONEPORT_MOCK_SUCCESS",
    )}
    try:
        _run_mission_load_and_start()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_start_with_orvd_topic_uses_mock_without_real_orvd():
    """При ORVD_TOPIC и AUTOPILOT_ORVD_MOCK_SUCCESS запрос к ОРВД по шине не нужен."""
    saved = {k: os.environ.pop(k, None) for k in (
        "ORVD_TOPIC",
        "DRONEPORT_TOPIC",
        "AUTOPILOT_ORVD_MOCK_SUCCESS",
        "AUTOPILOT_DRONEPORT_MOCK_SUCCESS",
    )}
    try:
        os.environ["ORVD_TOPIC"] = "v1.ORVD.ORVD001.main"
        os.environ["AUTOPILOT_ORVD_MOCK_SUCCESS"] = "1"
        _run_mission_load_and_start()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_start_with_droneport_topic_uses_mock_without_real_droneport():
    """При DRONEPORT_TOPIC и AUTOPILOT_DRONEPORT_MOCK_SUCCESS запросы к Дронопорту по шине не нужны."""
    saved = {k: os.environ.pop(k, None) for k in (
        "ORVD_TOPIC",
        "DRONEPORT_TOPIC",
        "AUTOPILOT_ORVD_MOCK_SUCCESS",
        "AUTOPILOT_DRONEPORT_MOCK_SUCCESS",
    )}
    try:
        os.environ["DRONEPORT_TOPIC"] = "v1.drone_port.1.drone_manager"
        os.environ["AUTOPILOT_DRONEPORT_MOCK_SUCCESS"] = "1"
        _run_mission_load_and_start()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def _run_mission_load_and_start():
    comp = _make_component()

    mission = {"mission_id": "m1", "steps": []}
    msg = {
        "action": "mission_load",
        "sender": SM_TOPIC,
        "payload": {"mission": mission},
    }
    result = comp._handle_mission_load(msg)
    assert result and result["ok"]

    cmd_msg = {
        "action": "cmd",
        "sender": SM_TOPIC,
        "payload": {"command": "START"},
    }
    cmd_result = comp._handle_cmd(cmd_msg)
    assert cmd_result and cmd_result["ok"]
    state = comp._handle_get_state({"action": "get_state"})
    assert state["state"] == "EXECUTING"


def test_mission_landing_finishes_and_returns_to_idle() -> None:
    comp = _make_component()
    comp._mission = {"mission_id": "m-land-1", "steps": [{"lat": 55.0, "lon": 37.0, "alt_m": 5.0}]}
    comp._state = "LANDING"
    comp._landing_active = True
    comp._last_nav_state = {"lat": 55.0, "lon": 37.0, "alt_m": 0.2, "heading_deg": 90.0}

    comp._step_control()

    state = comp._handle_get_state({"action": "get_state"})
    assert state["state"] == "IDLE"
    assert state["mission_id"] is None

