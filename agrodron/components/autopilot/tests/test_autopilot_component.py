from broker.system_bus import SystemBus
from components.autopilot.src.autopilot import AutopilotComponent


def _make_component() -> AutopilotComponent:
    bus = SystemBus()
    return AutopilotComponent(component_id="autopilot_test", bus=bus)


def test_mission_load_and_start():
    comp = _make_component()

    mission = {"mission_id": "m1", "steps": []}
    msg = {
        "action": "mission_load",
        "sender": "security_monitor_test",
        "payload": {"mission": mission},
    }
    result = comp._handle_mission_load(msg)
    assert result and result["ok"]

    cmd_msg = {
        "action": "cmd",
        "sender": "security_monitor_test",
        "payload": {"command": "START"},
    }
    cmd_result = comp._handle_cmd(cmd_msg)
    assert cmd_result and cmd_result["ok"]
    state = comp._handle_get_state({"action": "get_state"})
    assert state["state"] == "EXECUTING"

