from broker.system_bus import SystemBus
from systems.agrodron.src.mission_handler.src.mission_handler import MissionHandlerComponent
from systems.agrodron.src.mission_handler import config

SM_TOPIC = config.security_monitor_topic()


class DummyBus(SystemBus):
    def __init__(self):
        self.published = []
        self._response = None

    def publish(self, topic, message):
        self.published.append((topic, message))
        return True

    def subscribe(self, topic, callback):
        return True

    def unsubscribe(self, topic):
        return True

    def request(self, topic, message, timeout=30.0):
        # Имитация успешного ответа автопилота
        self.published.append((topic, message))
        return {"payload": {"ok": True}}

    async def request_async(self, topic, message, timeout=30.0):
        return self.request(topic, message, timeout)

    def start(self):
        pass

    def stop(self):
        pass


def _make_component() -> MissionHandlerComponent:
    bus = DummyBus()
    return MissionHandlerComponent(component_id="mission_handler_test", bus=bus)


# Минимальный валидный WPL: заголовок + одна точка (NAV_WAYPOINT, cmd=16)
WPL_SAMPLE = """QGC WPL 110
0	1	0	16	0	0	0	0	60.0	30.0	5.0	1"""


def test_load_mission_success():
    comp = _make_component()

    msg = {
        "action": "load_mission",
        "sender": SM_TOPIC,
        "payload": {
            "wpl_content": WPL_SAMPLE,
            "mission_id": "m1",
        },
    }

    result = comp._handle_load_mission(msg)
    assert result and result["ok"]
    assert comp._last_mission is not None
    assert comp._last_mission["mission_id"] == "m1"
    assert len(comp._last_mission["steps"]) >= 1


def test_load_mission_rejects_non_wpl():
    comp = _make_component()

    msg = {
        "action": "load_mission",
        "sender": SM_TOPIC,
        "payload": {
            "mission_id": "m1",
            "steps": [{"id": "wp-1", "lat": 60.0, "lon": 30.0, "alt_m": 5.0}],
        },
    }

    result = comp._handle_load_mission(msg)
    assert result is not None and not result.get("ok")
    assert result.get("error") == "invalid_input_wpl_required"


def test_validate_only_wpl():
    comp = _make_component()

    msg = {
        "action": "validate_only",
        "sender": SM_TOPIC,
        "payload": {"wpl_content": WPL_SAMPLE},
    }

    result = comp._handle_validate_only(msg)
    assert result and result["ok"]

