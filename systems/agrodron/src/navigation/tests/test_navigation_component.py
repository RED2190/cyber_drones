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
        "sender": SM_TOPIC,
        "payload": nav_payload,
    }
    result = comp._handle_nav_state(msg)
    assert result and result["ok"]

    state_msg = {"action": "get_state", "sender": SM_TOPIC, "payload": {}}
    state = comp._handle_get_state(state_msg)
    assert state is not None
    assert state["nav_state"] is not None
    assert state["nav_state"]["lat"] == nav_payload["lat"]

