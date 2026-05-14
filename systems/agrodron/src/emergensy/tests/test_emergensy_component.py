from systems.agrodron.src.bus_mock import MockSystemBus
from systems.agrodron.src.emergensy.src.emergensy import EmergenseyComponent
from systems.agrodron.src.emergensy import config

SM_TOPIC = config.security_monitor_topic()


def _make_component() -> EmergenseyComponent:
    bus = MockSystemBus()
    return EmergenseyComponent(component_id="emergensy_test", bus=bus)


def test_limiter_event_triggers_protocol():
    comp = _make_component()

    msg = {
        "action": "limiter_event",
        "sender": SM_TOPIC,
        "payload": {
            "event": "EMERGENCY_LAND_REQUIRED",
            "mission_id": "m1",
            "details": {},
        },
    }
    result = comp._handle_limiter_event(msg)
    assert result and result["ok"]
    state = comp._handle_get_state({"action": "get_state"})
    assert state["active"] is True

