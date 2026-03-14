from broker.system_bus import SystemBus
from components.emergensy.src.emergensy import EmergenseyComponent


def _make_component() -> EmergenseyComponent:
    bus = SystemBus()
    return EmergenseyComponent(component_id="emergensy_test", bus=bus)


def test_limiter_event_triggers_protocol():
    comp = _make_component()

    msg = {
        "action": "limiter_event",
        "sender": "security_monitor_test",
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

