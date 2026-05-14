from systems.agrodron.src.bus_mock import MockSystemBus
from systems.agrodron.src.limiter.src.limiter import LimiterComponent
from systems.agrodron.src.limiter import config

SM_TOPIC = config.security_monitor_topic()


def _make_component() -> LimiterComponent:
    bus = MockSystemBus()
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
        "sender": SM_TOPIC,
        "payload": {"mission": mission},
    }
    assert comp._handle_mission_load(msg)["ok"]

    nav_msg = {
        "action": "nav_state",
        "sender": SM_TOPIC,
        "payload": {"lat": 60.2, "lon": 30.2, "alt_m": 10.0},
    }
    assert comp._handle_nav_state(nav_msg)["ok"]

    state = comp._handle_get_state({"action": "get_state"})
    assert state["state"] in {"WARNING", "EMERGENCY"}

