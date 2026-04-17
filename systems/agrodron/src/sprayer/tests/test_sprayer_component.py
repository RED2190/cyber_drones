"""Unit-тесты компонента sprayer."""
import asyncio
from broker.system_bus import SystemBus
from systems.agrodron.src.sprayer.src.sprayer import SprayerComponent, SprayerState
from systems.agrodron.src.sprayer import config

SM_TOPIC = config.security_monitor_topic()


class DummyBus(SystemBus):
    def __init__(self):
        self.published: list = []

    def publish(self, topic, message):
        self.published.append((topic, message))
        return True

    def subscribe(self, topic, callback):
        return True

    def unsubscribe(self, topic):
        return True

    def request(self, topic, message, timeout=30.0):
        return None

    def request_async(self, topic, message, timeout=30.0):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        fut = loop.create_future()
        fut.set_result(self.request(topic, message, timeout))
        return fut

    def start(self):
        pass

    def stop(self):
        pass


def _make_component() -> SprayerComponent:
    bus = DummyBus()
    return SprayerComponent(component_id="sprayer_test", bus=bus)


def test_set_spray_on_trusted():
    comp = _make_component()
    msg = {
        "action": "set_spray",
        "sender": SM_TOPIC,
        "payload": {"spray": True},
    }
    result = comp._handle_set_spray(msg)
    assert result is not None and result["ok"]
    assert result["state"] == SprayerState.ON
    assert comp._state == SprayerState.ON


def test_set_spray_off_trusted():
    comp = _make_component()
    comp._state = SprayerState.ON
    msg = {
        "action": "set_spray",
        "sender": SM_TOPIC,
        "payload": {"spray": False},
    }
    result = comp._handle_set_spray(msg)
    assert result is not None and result["ok"]
    assert result["state"] == SprayerState.OFF


def test_set_spray_rejects_untrusted():
    comp = _make_component()
    msg = {
        "action": "set_spray",
        "sender": "unknown",
        "payload": {"spray": True},
    }
    result = comp._handle_set_spray(msg)
    assert result is None
    assert comp._state == SprayerState.OFF


def test_set_spray_invalid_payload():
    comp = _make_component()
    msg = {
        "action": "set_spray",
        "sender": SM_TOPIC,
        "payload": "not_a_dict",
    }
    result = comp._handle_set_spray(msg)
    assert result is not None and result.get("ok") is False


def test_get_state():
    comp = _make_component()
    comp._state = SprayerState.ON
    state = comp._handle_get_state({"action": "get_state"})
    assert state["state"] == SprayerState.ON
    assert "temperature_c" in state
    assert "tank_level_pct" in state
    assert "sitl_mode" in state


def test_state_change_publishes_to_security_monitor():
    comp = _make_component()
    bus = comp.bus
    msg = {
        "action": "set_spray",
        "sender": SM_TOPIC,
        "payload": {"spray": True},
    }
    comp._handle_set_spray(msg)
    assert len(bus.published) >= 1
    actions = [m.get("action") for _, m in bus.published]
    assert "proxy_publish" in actions
