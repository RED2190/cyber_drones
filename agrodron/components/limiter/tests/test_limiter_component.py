from broker.system_bus import SystemBus
from components.limiter.src.limiter import LimiterComponent


def _make_component() -> LimiterComponent:
    bus = SystemBus()
    return LimiterComponent(component_id="limiter_test", bus=bus)


def test_mission_and_nav_trigger_emergency():
    comp = _make_component()

    mission = {
        "mission_id": "m1",
        "steps": [
            {"id": "wp-001", "lat": 60.0, "lon": 30.0, "alt_m": 5.0},
        ],
    }
    msg = {
        "action": "mission_load",
        "sender": "security_monitor_test",
        "payload": {"mission": mission},
    }
    assert comp._handle_mission_load(msg)["ok"]

    nav_msg = {
        "action": "nav_state",
        "sender": "security_monitor_test",
        "payload": {"lat": 60.2, "lon": 30.2, "alt_m": 10.0},
    }
    assert comp._handle_nav_state(nav_msg)["ok"]

    state = comp._handle_get_state({"action": "get_state"})
    assert state["state"] in {"WARNING", "EMERGENCY"}

