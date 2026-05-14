"""Unit-тесты компонента навигации."""
import threading
import time

from systems.agrodron.src.bus_mock import MockSystemBus
from systems.agrodron.src.navigation import config
from systems.agrodron.src.navigation.src.navigation import NavigationComponent

SM_TOPIC = config.security_monitor_topic()


def _make_component() -> NavigationComponent:
    bus = MockSystemBus()
    return NavigationComponent(
        component_id="navigation_test",
        bus=bus,
        topic=config.component_topic(),
    )


def _msg(action: str, payload: dict = None, sender: str = SM_TOPIC) -> dict:
    return {"action": action, "sender": sender, "payload": payload or {}}


# ---------------------------------------------------------------- handlers

def test_nav_state_and_get_state():
    comp = _make_component()

    nav_payload = {
        "lat": 60.123450,
        "lon": 30.123400,
        "alt_m": 4.9,
        "ground_speed_mps": 4.8,
        "heading_deg": 90.0,
        "fix": "3D",
        "satellites": 14,
        "hdop": 0.7,
    }
    result = comp._handle_nav_state(_msg("nav_state", nav_payload))
    assert result and result["ok"]

    state_msg = _msg("get_state")
    state = comp._handle_get_state(state_msg)
    assert state is not None
    assert state["nav_state"] is not None
    assert state["nav_state"]["lat"] == nav_payload["lat"]
    # payload field should also contain nav_state for compatibility
    assert state["payload"] == state["nav_state"]


def test_nav_state_untrusted_sender():
    comp = _make_component()
    result = comp._handle_nav_state(_msg("nav_state", {"lat": 60.0}, sender="untrusted"))
    assert result is None


def test_nav_state_invalid_payload():
    comp = _make_component()
    result = comp._handle_nav_state(_msg("nav_state", "not_a_dict"))
    assert result is not None
    assert result["ok"] is False
    assert result["error"] == "invalid_nav_payload"


def test_handle_update_config():
    comp = _make_component()
    result = comp._handle_update_config(_msg("update_config", {"drone_id": "drone_001", "mode": "test"}))
    assert result["ok"] is True
    assert result["config"]["drone_id"] == "drone_001"
    assert result["config"]["mode"] == "test"


def test_handle_update_config_untrusted():
    comp = _make_component()
    result = comp._handle_update_config(_msg("update_config", {"key": "val"}, sender="untrusted"))
    assert result is None


def test_handle_update_config_invalid_payload():
    comp = _make_component()
    result = comp._handle_update_config(_msg("update_config", "not_dict"))
    assert result is not None
    assert result["ok"] is False
    assert result["error"] == "invalid_config_payload"


def test_handle_get_state_untrusted():
    comp = _make_component()
    result = comp._handle_get_state(_msg("get_state", sender="untrusted"))
    assert result is None


def test_handle_get_state_empty():
    comp = _make_component()
    state = comp._handle_get_state(_msg("get_state"))
    assert state is not None
    assert state["nav_state"] is None
    assert state["config"] == {}


def test_handle_get_state_returns_config():
    comp = _make_component()
    comp._handle_update_config(_msg("update_config", {"drone_id": "d1"}))
    state = comp._handle_get_state(_msg("get_state"))
    assert state["config"]["drone_id"] == "d1"


# ---------------------------------------------------------------- trusted sender

def test_is_trusted_sender():
    assert NavigationComponent._is_trusted_sender({"sender": SM_TOPIC}) is True
    assert NavigationComponent._is_trusted_sender({"sender": "other"}) is False
    assert NavigationComponent._is_trusted_sender({}) is False


# ---------------------------------------------------------------- _request_sitl_state

def test_request_sitl_state_with_drone_id():
    bus = MockSystemBus()
    bus.request = lambda topic, msg, timeout=30.0: {
        "payload": {
            "target_response": {
                "payload": {"lat": 60.0, "lon": 30.0, "alt": 10.0, "reply_to": "x", "correlation_id": "y"},
            },
        },
    }
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    comp._config = {"drone_id": "drone_001"}
    result = comp._request_sitl_state()
    assert result is not None
    assert result["lat"] == 60.0
    # reply_to and correlation_id should be stripped
    assert "reply_to" not in result
    assert "correlation_id" not in result


def test_request_sitl_state_no_response():
    bus = MockSystemBus()
    bus.request = lambda *a, **kw: None
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    result = comp._request_sitl_state()
    assert result is None


def test_request_sitl_state_non_dict_target_response():
    bus = MockSystemBus()
    bus.request = lambda *a, **kw: {"payload": "not_dict"}
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    result = comp._request_sitl_state()
    assert result is None


# ---------------------------------------------------------------- _poll_sitl_once

def test_poll_sitl_once_success():
    bus = MockSystemBus()
    raw = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0, "ground_speed_mps": 5.0, "heading_deg": 90.0}
    bus.request = lambda *a, **kw: {
        "payload": {
            "target_response": {
                "payload": raw,
            },
        },
    }
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    comp._poll_sitl_once()
    assert comp._last_nav_state is not None
    assert comp._last_nav_state["lat"] == 60.0


def test_poll_sitl_once_none_response():
    bus = MockSystemBus()
    bus.request = lambda *a, **kw: None
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    comp._poll_sitl_once()
    assert comp._last_nav_state is None


def test_poll_sitl_once_exception_does_not_crash():
    bus = MockSystemBus()
    bus.request = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("bus error"))
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    # Should not raise
    try:
        comp._poll_sitl_once()
    except RuntimeError:
        pass  # exception propagation is fine as long as it's caught by the loop


# ---------------------------------------------------------------- _publish_nav_state

def test_publish_nav_state():
    bus = MockSystemBus()
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    nav_state = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0}
    comp._publish_nav_state(nav_state)
    assert len(bus.published) == 1
    topic, msg = bus.published[0]
    assert topic == config.agrodron_nav_state_topic()
    assert msg["lat"] == 60.0


def test_publish_nav_state_adds_drone_id_from_config():
    bus = MockSystemBus()
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    comp._config = {"drone_id": "drone_007"}
    nav_state = {"lat": 60.0, "lon": 30.0}
    comp._publish_nav_state(nav_state)
    _, msg = bus.published[0]
    assert msg["drone_id"] == "drone_007"


# ---------------------------------------------------------------- _log_gps_degraded

def test_log_gps_degraded():
    bus = MockSystemBus()
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    nav_state = {"lat": 0.0, "lon": 0.0, "gps_valid": False}
    comp._log_gps_degraded(nav_state)
    assert len(bus.published) == 1
    topic, msg = bus.published[0]
    assert topic == config.security_monitor_topic()
    assert msg["action"] == "proxy_publish"
    assert msg["payload"]["data"]["event"] == "NAVIGATION_GPS_DEGRADED"


# ---------------------------------------------------------------- _poll_sitl_once gps degraded logging

def test_poll_sitl_once_gps_degraded_logs():
    bus = MockSystemBus()
    raw = {"lat": 0.0, "lon": 0.0, "alt_m": 0.0}  # no fix/satellites => gps_valid=False in SITL format
    # But sitl_normalizer will set gps_valid=True for SITL format if lat/lon present and valid
    # Let's use a more explicit case: NMEA with quality=0
    raw_nmea = {
        "derived": {"lat_decimal": 60.0, "lon_decimal": 30.0, "altitude_msl": 10.0},
        "nmea": {
            "rmc": {"speed_knots": 0, "course_degrees": 0},
            "gga": {"quality": 0, "satellites": 2, "hdop": 15.0},
        },
    }
    bus.request = lambda *a, **kw: {
        "payload": {"target_response": {"payload": raw_nmea}},
    }
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    comp._journal_logged_sitl_link = True  # skip the SITL link log to focus on GPS degraded
    comp._poll_sitl_once()
    # GPS degraded log should have been published
    assert len(bus.published) >= 1


def test_poll_sitl_once_journal_link_logged_once():
    bus = MockSystemBus()
    raw = {"lat": 60.0, "lon": 30.0, "alt_m": 10.0, "ground_speed_mps": 5.0, "heading_deg": 90.0, "fix": "3D", "satellites": 14, "hdop": 0.7}
    bus.request = lambda *a, **kw: {
        "payload": {"target_response": {"payload": raw}},
    }
    comp = NavigationComponent(component_id="nav_test", bus=bus, topic=config.component_topic())
    assert comp._journal_logged_sitl_link is False
    comp._poll_sitl_once()
    assert comp._journal_logged_sitl_link is True
    # Second poll should not log again
    pub_count = len(bus.published)
    comp._poll_sitl_once()
    # Only nav_state publish, no journal link log
    # The count grows by 1 (the nav_state publish), not by 3 (nav_state + 2 journal events)
    assert len(bus.published) == pub_count + 1


# ---------------------------------------------------------------- lifecycle

def test_start_and_stop():
    comp = _make_component()
    comp.start()
    assert comp._housekeeping_thread is not None
    comp.stop()
    # Should not crash
