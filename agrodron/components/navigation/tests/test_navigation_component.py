from broker.system_bus import SystemBus
from components.navigation import config
from components.navigation.src.navigation import NavigationComponent


def _make_component() -> NavigationComponent:
    bus = SystemBus()
    return NavigationComponent(
        component_id="navigation_test",
        bus=bus,
        topic=config.component_topic(),
    )


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
    msg = {
        "action": "nav_state",
        "sender": "security_monitor_test",
        "payload": nav_payload,
    }
    result = comp._handle_nav_state(msg)
    assert result and result["ok"]

    state_msg = {"action": "get_state", "sender": "security_monitor_test", "payload": {}}
    state = comp._handle_get_state(state_msg)
    assert state is not None
    assert state["nav_state"] is not None
    assert state["nav_state"]["lat"] == nav_payload["lat"]

