"""Unit-тесты компонента autopilot."""
import os
import math
import threading
import time

from systems.agrodron.src.bus_mock import MockSystemBus
from systems.agrodron.src.autopilot.src.autopilot import AutopilotComponent
from systems.agrodron.src.autopilot import config

SM_TOPIC = config.security_monitor_topic()


def _make_component(**overrides) -> AutopilotComponent:
    bus = MockSystemBus()
    comp = AutopilotComponent(component_id="autopilot_test", bus=bus, **overrides)
    return comp


def _msg(action: str, payload: dict = None, sender: str = SM_TOPIC) -> dict:
    return {"action": action, "sender": sender, "payload": payload or {}}


# ------------------------------------------------------------------ handlers

def test_mission_load_and_start():
    """mission_load → START → PRE_FLIGHT (not EXECUTING, new logic)."""
    saved = {k: os.environ.pop(k, None) for k in ("ORVD_TOPIC", "DRONEPORT_TOPIC")}
    try:
        comp = _make_component()
        mission = {"mission_id": "m1", "steps": []}
        result = comp._handle_mission_load(_msg("mission_load", {"mission": mission}))
        assert result and result["ok"]
        assert result["state"] == "MISSION_LOADED"

        cmd_result = comp._handle_cmd(_msg("cmd", {"command": "START"}))
        assert cmd_result and cmd_result["ok"]
        # New logic: START -> PRE_FLIGHT, not EXECUTING
        assert cmd_result["state"] == "PRE_FLIGHT"

        state = comp._handle_get_state(_msg("get_state"))
        assert state["state"] == "PRE_FLIGHT"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_mission_load_untrusted_sender():
    comp = _make_component()
    result = comp._handle_mission_load(_msg("mission_load", {"mission": {"mission_id": "x"}}, sender="untrusted"))
    assert result is None


def test_mission_load_invalid_payload():
    comp = _make_component()
    result = comp._handle_mission_load(_msg("mission_load", {"mission": "not_a_dict"}))
    assert result is not None and result["ok"] is False
    assert result["error"] == "invalid_mission"


def test_mission_load_no_mission_key():
    comp = _make_component()
    result = comp._handle_mission_load(_msg("mission_load", {}))
    assert result is not None and result["ok"] is False


def test_cmd_start_no_mission():
    saved = {k: os.environ.pop(k, None) for k in ("ORVD_TOPIC", "DRONEPORT_TOPIC")}
    try:
        comp = _make_component()
        # Set wait time to 0 to avoid blocking
        comp._start_mission_wait_s = 0.0
        result = comp._handle_cmd(_msg("cmd", {"command": "START"}))
        assert result["ok"] is False
        assert result["error"] == "no_mission"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_cmd_start_invalid_state():
    comp = _make_component()
    comp._state = "EXECUTING"
    comp._mission = {"mission_id": "m1", "steps": []}
    result = comp._handle_cmd(_msg("cmd", {"command": "START"}))
    assert result["ok"] is False
    assert result["error"] == "invalid_state_for_start"


def test_cmd_pause():
    comp = _make_component()
    comp._state = "EXECUTING"
    result = comp._handle_cmd(_msg("cmd", {"command": "PAUSE"}))
    assert result["ok"] is True
    assert result["state"] == "PAUSED"


def test_cmd_resume():
    comp = _make_component()
    comp._state = "PAUSED"
    result = comp._handle_cmd(_msg("cmd", {"command": "RESUME"}))
    assert result["ok"] is True
    assert result["state"] == "EXECUTING"


def test_cmd_abort():
    comp = _make_component()
    comp._state = "EXECUTING"
    result = comp._handle_cmd(_msg("cmd", {"command": "ABORT"}))
    assert result["ok"] is True
    assert result["state"] == "ABORTED"


def test_cmd_reset():
    comp = _make_component()
    comp._state = "EXECUTING"
    comp._mission = {"mission_id": "m1", "steps": [1]}
    comp._current_step_index = 0
    result = comp._handle_cmd(_msg("cmd", {"command": "RESET"}))
    assert result["ok"] is True
    assert result["state"] == "IDLE"
    assert comp._mission is None
    assert comp._current_step_index is None


def test_cmd_emergency_stop():
    comp = _make_component()
    comp._state = "EXECUTING"
    result = comp._handle_cmd(_msg("cmd", {"command": "EMERGENCY_STOP"}))
    assert result["ok"] is True
    assert result["state"] == "EMERGENCY_STOP"


def test_cmd_kover():
    comp = _make_component()
    comp._state = "EXECUTING"
    result = comp._handle_cmd(_msg("cmd", {"command": "KOVER"}))
    assert result["ok"] is True
    assert comp._kover_active is True


def test_cmd_kover_from_paused():
    comp = _make_component()
    comp._state = "PAUSED"
    result = comp._handle_cmd(_msg("cmd", {"command": "KOVER"}))
    assert result["ok"] is True
    assert comp._kover_active is True
    # Should stay PAUSED (state not changed)
    assert result["state"] == "PAUSED"


def test_cmd_kover_from_idle():
    comp = _make_component()
    comp._state = "IDLE"
    result = comp._handle_cmd(_msg("cmd", {"command": "KOVER"}))
    assert result["ok"] is True
    assert comp._kover_active is True
    # Should switch to EXECUTING for control loop
    assert result["state"] == "EXECUTING"


def test_cmd_unknown():
    comp = _make_component()
    result = comp._handle_cmd(_msg("cmd", {"command": "DO_SOMETHING"}))
    assert result["ok"] is False
    assert result["error"] == "unknown_command"


def test_cmd_untrusted_sender():
    comp = _make_component()
    result = comp._handle_cmd(_msg("cmd", {"command": "PAUSE"}, sender="untrusted"))
    assert result is None


def test_get_state():
    comp = _make_component()
    comp._mission = {"mission_id": "m1", "steps": [{"lat": 1}, {"lat": 2}]}
    comp._current_step_index = 1
    comp._state = "EXECUTING"
    comp._sprayer_state = "ON"
    comp._last_nav_state = {"lat": 60.0}

    result = comp._handle_get_state(_msg("get_state"))
    assert result["state"] == "EXECUTING"
    assert result["mission_id"] == "m1"
    assert result["current_step_index"] == 1
    assert result["total_steps"] == 2
    assert result["sprayer_state"] == "ON"
    assert result["last_nav_state"] == {"lat": 60.0}


# ------------------------------------------------------------------ navigation poll

def test_poll_navigation_unwraps_nested_proxy_response():
    comp = _make_component()
    nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0, "heading_deg": 90.0}

    comp.bus.request = lambda *args, **kwargs: {
        "success": True,
        "payload": {
            "target_response": {
                "success": True,
                "payload": {
                    "nav_state": nav_state,
                    "payload": nav_state,
                },
            },
        },
    }

    comp._poll_navigation_if_due()
    assert comp._last_nav_state == nav_state


def test_poll_navigation_skips_if_not_due():
    comp = _make_component()
    comp._last_nav_poll_ts = time.monotonic()
    old_state = comp._last_nav_state
    comp._poll_navigation_if_due()
    assert comp._last_nav_state == old_state


# ------------------------------------------------------------------ pre-flight / ORVD / DronePort

def test_request_departure_orvd_unwraps_nested_proxy_response():
    saved_orvd_topic = os.environ.get("ORVD_TOPIC")
    os.environ["ORVD_TOPIC"] = "v1.ORVD.ORVD001.main"
    try:
        comp = _make_component()
        comp.bus.request = lambda *args, **kwargs: {
            "success": True,
            "payload": {
                "target_response": {
                    "success": True,
                    "payload": {
                        "status": "takeoff_authorized",
                        "mission_id": "m1",
                    },
                },
            },
        }
        assert comp._request_departure_orvd("m1") is True
    finally:
        if saved_orvd_topic is None:
            os.environ.pop("ORVD_TOPIC", None)
        else:
            os.environ["ORVD_TOPIC"] = saved_orvd_topic


def test_request_departure_orvd_no_topic():
    saved = os.environ.pop("ORVD_TOPIC", None)
    try:
        comp = _make_component()
        # Empty topic -> True (skip ORVD check)
        assert comp._request_departure_orvd("m1") is True
    finally:
        if saved is not None:
            os.environ["ORVD_TOPIC"] = saved


def test_request_departure_orvd_mock_success():
    saved_topic = os.environ.get("ORVD_TOPIC")
    saved_mock = os.environ.get("AUTOPILOT_ORVD_MOCK_SUCCESS")
    os.environ["ORVD_TOPIC"] = "v1.ORVD.test"
    os.environ["AUTOPILOT_ORVD_MOCK_SUCCESS"] = "true"
    try:
        comp = _make_component()
        assert comp._request_departure_orvd("m1") is True
    finally:
        if saved_topic is None:
            os.environ.pop("ORVD_TOPIC", None)
        else:
            os.environ["ORVD_TOPIC"] = saved_topic
        if saved_mock is None:
            os.environ.pop("AUTOPILOT_ORVD_MOCK_SUCCESS", None)
        else:
            os.environ["AUTOPILOT_ORVD_MOCK_SUCCESS"] = saved_mock


def test_request_departure_orvd_denied():
    saved_topic = os.environ.get("ORVD_TOPIC")
    os.environ["ORVD_TOPIC"] = "v1.ORVD.test"
    try:
        comp = _make_component()
        comp.bus.request = lambda *args, **kwargs: {
            "payload": {
                "target_response": {
                    "payload": {"status": "denied"},
                },
            },
        }
        assert comp._request_departure_orvd("m1") is False
    finally:
        if saved_topic is None:
            os.environ.pop("ORVD_TOPIC", None)
        else:
            os.environ["ORVD_TOPIC"] = saved_topic


def test_request_takeoff_droneport_no_topic():
    saved = os.environ.pop("DRONEPORT_TOPIC", None)
    try:
        comp = _make_component()
        assert comp._request_takeoff_droneport("m1") is True
    finally:
        if saved is not None:
            os.environ["DRONEPORT_TOPIC"] = saved


def test_request_takeoff_droneport_mock():
    saved_topic = os.environ.get("DRONEPORT_TOPIC")
    saved_mock = os.environ.get("AUTOPILOT_DRONEPORT_MOCK_SUCCESS")
    os.environ["DRONEPORT_TOPIC"] = "v1.DP.test"
    os.environ["AUTOPILOT_DRONEPORT_MOCK_SUCCESS"] = "true"
    try:
        comp = _make_component()
        assert comp._request_takeoff_droneport("m1") is True
    finally:
        if saved_topic is None:
            os.environ.pop("DRONEPORT_TOPIC", None)
        else:
            os.environ["DRONEPORT_TOPIC"] = saved_topic
        if saved_mock is None:
            os.environ.pop("AUTOPILOT_DRONEPORT_MOCK_SUCCESS", None)
        else:
            os.environ["AUTOPILOT_DRONEPORT_MOCK_SUCCESS"] = saved_mock


def test_request_landing_droneport_no_topic():
    saved = os.environ.pop("DRONEPORT_TOPIC", None)
    try:
        comp = _make_component()
        assert comp._request_landing_droneport() is True
    finally:
        if saved is not None:
            os.environ["DRONEPORT_TOPIC"] = saved


def test_request_landing_droneport_mock():
    saved_topic = os.environ.get("DRONEPORT_TOPIC")
    saved_mock = os.environ.get("AUTOPILOT_DRONEPORT_MOCK_SUCCESS")
    os.environ["DRONEPORT_TOPIC"] = "v1.DP.test"
    os.environ["AUTOPILOT_DRONEPORT_MOCK_SUCCESS"] = "true"
    try:
        comp = _make_component()
        assert comp._request_landing_droneport() is True
    finally:
        if saved_topic is None:
            os.environ.pop("DRONEPORT_TOPIC", None)
        else:
            os.environ["DRONEPORT_TOPIC"] = saved_topic
        if saved_mock is None:
            os.environ.pop("AUTOPILOT_DRONEPORT_MOCK_SUCCESS", None)
        else:
            os.environ["AUTOPILOT_DRONEPORT_MOCK_SUCCESS"] = saved_mock


# ------------------------------------------------------------------ velocity vectors

def test_compute_velocity_vectors_north():
    comp = _make_component()
    vx, vy, vz = comp._compute_velocity_vectors(
        heading_deg=0.0, ground_speed_mps=5.0, current_alt=10.0, target_alt=10.0,
    )
    assert abs(vx) < 0.01
    assert abs(vy - 5.0) < 0.01
    assert abs(vz) < 0.01  # alt diff < 0.2


def test_compute_velocity_vectors_climb():
    comp = _make_component()
    vx, vy, vz = comp._compute_velocity_vectors(
        heading_deg=0.0, ground_speed_mps=5.0, current_alt=10.0, target_alt=20.0,
    )
    assert vz > 0  # climbing


def test_compute_velocity_vectors_descend():
    comp = _make_component()
    vx, vy, vz = comp._compute_velocity_vectors(
        heading_deg=0.0, ground_speed_mps=5.0, current_alt=20.0, target_alt=10.0,
    )
    assert vz < 0  # descending


def test_compute_velocity_vectors_east():
    comp = _make_component()
    vx, vy, vz = comp._compute_velocity_vectors(
        heading_deg=90.0, ground_speed_mps=5.0, current_alt=10.0, target_alt=10.0,
    )
    assert abs(vx - 5.0) < 0.01
    assert abs(vy) < 0.01


# ------------------------------------------------------------------ _step_control

def test_step_control_preflight_orvd_denied():
    saved = {k: os.environ.pop(k, None) for k in ("ORVD_TOPIC", "DRONEPORT_TOPIC")}
    try:
        comp = _make_component()
        comp._state = "PRE_FLIGHT"
        comp._mission = {"mission_id": "m1", "steps": []}
        comp._last_nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0}

        # ORVD denied (non-empty topic, but request returns denied)
        os.environ["ORVD_TOPIC"] = "v1.ORVD.test"
        comp.bus.request = lambda *a, **kw: {"payload": {"target_response": {"payload": {"status": "denied"}}}}

        comp._step_control()
        assert comp._state == "ABORTED"
        assert comp._last_error == "orvd_denied"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_step_control_preflight_success():
    saved = {k: os.environ.pop(k, None) for k in ("ORVD_TOPIC", "DRONEPORT_TOPIC")}
    try:
        comp = _make_component()
        comp._state = "PRE_FLIGHT"
        comp._mission = {"mission_id": "m1", "steps": []}
        comp._last_nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0}

        # Both ORVD and DronePort mock success
        os.environ["AUTOPILOT_ORVD_MOCK_SUCCESS"] = "true"
        os.environ["AUTOPILOT_DRONEPORT_MOCK_SUCCESS"] = "true"

        comp._step_control()
        assert comp._state == "EXECUTING"
    finally:
        for k in ("ORVD_TOPIC", "DRONEPORT_TOPIC", "AUTOPILOT_ORVD_MOCK_SUCCESS", "AUTOPILOT_DRONEPORT_MOCK_SUCCESS"):
            os.environ.pop(k, None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_step_control_no_nav_state():
    comp = _make_component()
    comp._last_nav_state = None
    comp._state = "EXECUTING"
    # Should return early
    comp._step_control()
    assert comp._state == "EXECUTING"  # unchanged


def test_step_control_kover_active_landed():
    comp = _make_component()
    comp._kover_active = True
    comp._state = "EXECUTING"
    comp._last_nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 0.3, "heading_deg": 0.0}

    comp._step_control()
    assert comp._kover_active is False
    assert comp._state == "PAUSED"


def test_step_control_kover_active_still_flying():
    comp = _make_component()
    comp._kover_active = True
    comp._state = "EXECUTING"
    comp._last_nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0, "heading_deg": 0.0}

    comp._step_control()
    assert comp._kover_active is True  # still descending
    assert comp._state == "EXECUTING"


def test_step_control_executing_paused_hold_position():
    comp = _make_component()
    comp._state = "PAUSED"
    comp._mission = {"mission_id": "m1", "steps": [{"lat": 60.0, "lon": 30.0, "alt_m": 10.0}]}
    comp._current_step_index = 0
    comp._last_nav_state = {"lat": 59.9, "lon": 29.9, "alt_m": 10.0, "heading_deg": 90.0}

    comp._step_control()
    # Should stay paused and send hold position
    assert comp._state == "PAUSED"


def test_step_control_executing_move_to_target():
    comp = _make_component()
    comp._state = "EXECUTING"
    comp._mission = {"mission_id": "m1", "steps": [{"lat": 60.5, "lon": 30.5, "alt_m": 10.0, "speed_mps": 3.0}]}
    comp._current_step_index = 0
    comp._last_nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0, "heading_deg": 45.0}

    comp._step_control()
    # Should have published to motors via bus
    assert len(comp.bus.published) > 0


def test_step_control_mission_completed():
    comp = _make_component()
    comp._state = "EXECUTING"
    comp._mission = {"mission_id": "m1", "steps": [{"lat": 60.0, "lon": 30.0, "alt_m": 10.0}]}
    comp._current_step_index = 1  # beyond last step

    comp._last_nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0, "heading_deg": 0.0}

    comp._step_control()
    assert comp._state == "COMPLETED"


# ------------------------------------------------------------------ droneport helpers

def test_droneport_battery_pct_from_nav():
    comp = _make_component()
    comp._last_nav_state = {"battery_pct": 85.5, "lat": 0.0}
    assert comp._droneport_battery_pct(default=50.0) == 85.5


def test_droneport_battery_pct_from_battery_key():
    comp = _make_component()
    comp._last_nav_state = {"battery": 75.0}
    assert comp._droneport_battery_pct(default=50.0) == 75.0


def test_droneport_battery_pct_default():
    comp = _make_component()
    comp._last_nav_state = {}
    assert comp._droneport_battery_pct(default=50.0) == 50.0


def test_unwrap_droneport_response_with_port_id():
    resp = {"port_id": "P1", "battery": 80}
    result = AutopilotComponent._unwrap_droneport_response(resp)
    assert result is not None
    assert result.get("port_id") == "P1"


def test_unwrap_droneport_response_with_error():
    resp = {"error": "busy"}
    result = AutopilotComponent._unwrap_droneport_response(resp)
    assert result is not None
    assert result.get("error") == "busy"


def test_unwrap_droneport_response_none():
    result = AutopilotComponent._unwrap_droneport_response(None)
    assert result is None


def test_droneport_takeoff_ok():
    comp = _make_component()
    resp = {"port_id": "P1", "battery": 80}
    assert comp._droneport_takeoff_ok(resp) is True


def test_droneport_takeoff_ok_with_battery_key():
    comp = _make_component()
    resp = {"battery": 80}
    assert comp._droneport_takeoff_ok(resp) is True


def test_droneport_takeoff_denied():
    comp = _make_component()
    resp = {"error": "busy"}
    assert comp._droneport_takeoff_ok(resp) is False


def test_droneport_landing_ok():
    comp = _make_component()
    resp = {"port_id": "P1"}
    assert comp._droneport_landing_ok(resp) is True


def test_droneport_landing_denied():
    comp = _make_component()
    resp = {"error": "no_ports"}
    assert comp._droneport_landing_ok(resp) is False


# ------------------------------------------------------------------ proxy helpers

def test_unwrap_proxy_target_response_direct():
    resp = {"payload": {"answer": 42}}
    result = AutopilotComponent._unwrap_proxy_target_response(resp)
    # No target_response -> returns original response dict
    assert result == {"payload": {"answer": 42}}


def test_unwrap_proxy_target_response_with_target():
    resp = {"payload": {"target_response": {"payload": {"answer": 42}}}}
    result = AutopilotComponent._unwrap_proxy_target_response(resp)
    # target_response found -> returns its payload
    assert result == {"answer": 42}


def test_unwrap_proxy_target_response_none_input():
    result = AutopilotComponent._unwrap_proxy_target_response(None)
    assert result is None


def test_proxy_request_external_no_topic():
    comp = _make_component()
    result = comp._proxy_request_external("", "action", {})
    assert result is None


def test_proxy_request_external_non_dict_response():
    comp = _make_component()
    comp.bus.request = lambda *a, **kw: None
    result = comp._proxy_request_external("some.topic", "action", {})
    assert result is None


def test_notify_nus_no_topic():
    saved = os.environ.pop("NUS_TOPIC", None)
    try:
        comp = _make_component()
        comp._notify_nus("event", {})  # should not raise
    finally:
        if saved is not None:
            os.environ["NUS_TOPIC"] = saved


# ------------------------------------------------------------------ send helpers

def test_send_motors_target():
    comp = _make_component()
    comp._send_motors_target(vx=1.0, vy=0.0, vz=0.0, alt_m=10.0, lat=60.0, lon=30.0, heading_deg=0.0)
    assert len(comp.bus.published) == 1
    topic, msg = comp.bus.published[0]
    assert msg["action"] == "proxy_publish"
    assert msg["payload"]["data"]["vx"] == 1.0


def test_send_sprayer_on():
    comp = _make_component()
    comp._send_sprayer(True)
    assert comp._sprayer_state == "ON"
    assert len(comp.bus.published) == 1


def test_send_sprayer_off():
    comp = _make_component()
    comp._send_sprayer(False)
    assert comp._sprayer_state == "OFF"


# ------------------------------------------------------------------ trusted sender

def test_is_trusted_sender():
    assert AutopilotComponent._is_trusted_sender({"sender": SM_TOPIC}) is True
    assert AutopilotComponent._is_trusted_sender({"sender": "other"}) is False
    assert AutopilotComponent._is_trusted_sender({}) is False


# ------------------------------------------------------------------ landing

def test_start_mission_landing():
    saved = {k: os.environ.pop(k, None) for k in ("DRONEPORT_TOPIC",)}
    try:
        comp = _make_component()
        comp._state = "EXECUTING"
        comp._mission = {"mission_id": "m1", "steps": []}
        comp._start_mission_landing("m1")
        assert comp._landing_active is True
        assert comp._state == "LANDING"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_handle_mission_landing_on_ground():
    comp = _make_component()
    comp._landing_active = True
    comp._landing_port_confirmed = True
    comp._last_nav_state = {"alt_m": 0.3, "lat": 60.0, "lon": 30.0, "heading_deg": 0.0}
    comp._mission = {"mission_id": "m1"}

    comp._handle_mission_landing()
    assert comp._landing_active is False
    assert comp._state == "IDLE"
    assert comp._mission is None


def test_handle_mission_landing_descending():
    comp = _make_component()
    comp._landing_active = True
    comp._landing_port_confirmed = True
    comp._last_nav_state = {"alt_m": 5.0, "lat": 60.0, "lon": 30.0, "heading_deg": 0.0}
    comp._mission = {"mission_id": "m1"}
    comp._state = "LANDING"

    comp._handle_mission_landing()
    assert comp._landing_active is True  # still descending
    assert comp._state == "LANDING"  # still in landing mode


def test_handle_mission_landing_no_nav():
    comp = _make_component()
    comp._landing_active = True
    comp._last_nav_state = None
    comp._handle_mission_landing()  # should not raise


def test_self_diagnostics():
    comp = _make_component()
    assert comp._self_diagnostics() is True


# ------------------------------------------------------------------ wait for mission

def test_wait_for_mission_before_start_zero_timeout():
    comp = _make_component()
    comp._start_mission_wait_s = 0.0
    comp._mission = None
    assert comp._wait_for_mission_before_start() is False


def test_wait_for_mission_before_start_already_loaded():
    comp = _make_component()
    comp._start_mission_wait_s = 1.0
    comp._mission = {"mission_id": "m1", "steps": []}
    assert comp._wait_for_mission_before_start() is True


def test_request_charging_droneport_no_topic():
    saved = os.environ.pop("DRONEPORT_TOPIC", None)
    try:
        comp = _make_component()
        comp._request_charging_droneport()  # should not raise
    finally:
        if saved is not None:
            os.environ["DRONEPORT_TOPIC"] = saved
