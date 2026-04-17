"""Unit-тесты компонента motors."""
import asyncio
from broker.system_bus import SystemBus
from systems.agrodron.src.motors.src.motors import MotorsComponent, MotorsMode
from systems.agrodron.src.motors import config

SM_TOPIC = config.security_monitor_topic()


class DummyBus(SystemBus):
    """Шина с записью вызовов publish."""

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


def _make_component() -> MotorsComponent:
    bus = DummyBus()
    return MotorsComponent(component_id="motors_test", bus=bus)


def test_set_target_trusted_sender():
    comp = _make_component()
    msg = {
        "action": "set_target",
        "sender": SM_TOPIC,
        "payload": {"vx": 1.0, "vy": 0.5, "vz": 0.0},
    }
    result = comp._handle_set_target(msg)
    assert result is not None and result["ok"] is True
    assert result["mode"] == MotorsMode.TRACKING
    assert comp._last_target["vx"] == 1.0 and comp._last_target["vy"] == 0.5


def test_set_target_rejects_untrusted_sender():
    comp = _make_component()
    msg = {
        "action": "set_target",
        "sender": "unknown",
        "payload": {"vx": 1.0, "vy": 0.0, "vz": 0.0},
    }
    result = comp._handle_set_target(msg)
    assert result is None


def test_set_target_heading_speed_fallback():
    comp = _make_component()
    msg = {
        "action": "set_target",
        "sender": SM_TOPIC,
        "payload": {"heading_deg": 90.0, "ground_speed_mps": 2.0},
    }
    result = comp._handle_set_target(msg)
    assert result is not None and result["ok"]
    # 90° = East: vx > 0, vy ≈ 0
    assert abs(comp._last_target["vx"] - 2.0) < 0.01
    assert abs(comp._last_target["vy"]) < 0.01


def test_land_trusted_sender():
    comp = _make_component()
    comp._last_target = {"vx": 1.0, "vy": 0.0, "vz": 0.0}
    msg = {"action": "land", "sender": SM_TOPIC, "payload": {}}
    result = comp._handle_land(msg)
    assert result is not None and result["ok"]
    assert result["mode"] == MotorsMode.LANDING


def test_land_rejects_untrusted():
    comp = _make_component()
    msg = {"action": "land", "sender": "stranger", "payload": {}}
    result = comp._handle_land(msg)
    assert result is None


def test_get_state():
    comp = _make_component()
    comp._mode = MotorsMode.TRACKING
    comp._last_target = {"vx": 1.0, "vy": 0.0}
    state = comp._handle_get_state({"action": "get_state"})
    assert state["mode"] == MotorsMode.TRACKING
    assert state["last_target"]["vx"] == 1.0


def test_build_sitl_command_format():
    comp = _make_component()
    cmd = comp._build_sitl_command({"vx": 1.0, "vy": 0.5, "vz": -0.2})
    assert "drone_id" in cmd
    assert cmd["vx"] == 1.0 and cmd["vy"] == 0.5 and cmd["vz"] == -0.2
    assert 0 <= cmd["mag_heading"] <= 360
    assert set(cmd.keys()) == {"drone_id", "vx", "vy", "vz", "mag_heading"}


def test_build_sitl_command_clamps_limits():
    comp = _make_component()
    cmd = comp._build_sitl_command({"vx": 100.0, "vy": -60.0, "vz": -15.0})
    assert cmd["vx"] == 50.0
    assert cmd["vy"] == -50.0
    assert cmd["vz"] == -10.0


def test_emit_sitl_publishes_to_security_monitor():
    comp = _make_component()
    bus = comp.bus
    assert isinstance(bus, DummyBus)
    comp._emit_sitl_command({"vx": 0.0, "vy": 0.0, "vz": 0.0})
    # 1) команда SITL __raw__; 2) запись в журнал (веб-монитор)
    assert len(bus.published) == 2
    _topic, message = bus.published[0]
    assert message.get("action") == "proxy_publish"
    assert message.get("payload", {}).get("target", {}).get("action") == "__raw__"
    _jt, jmsg = bus.published[1]
    assert jmsg.get("action") == "proxy_publish"
    assert jmsg.get("payload", {}).get("target", {}).get("action") == "log_event"
