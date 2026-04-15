"""Integration tests: end-to-end mission flow."""
import json
import os

from agrodron.tests.integration.integration_bus import IntegrationBus
from systems.agrodron.src.sdk.topic_utils import topic_for

from systems.agrodron.src.security_monitor.src.security_monitor import SecurityMonitorComponent
from systems.agrodron.src.autopilot.src.autopilot import AutopilotComponent
from systems.agrodron.src.mission_handler.src.mission_handler import MissionHandlerComponent
from systems.agrodron.src.journal.src.journal import JournalComponent


WPL_SAMPLE = "QGC WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60.0\t30.0\t5.0\t1"

NUS_TOPIC = os.environ.get("NUS_TOPIC", "v1.NUS.NUS001.main")


def _build_policies():
    return json.dumps([
        {"sender": topic_for("mission_handler"), "topic": topic_for("autopilot"), "action": "mission_load"},
        {"sender": topic_for("mission_handler"), "topic": topic_for("journal"), "action": "log_event"},
        {"sender": topic_for("autopilot"), "topic": topic_for("journal"), "action": "log_event"},
        {"sender": NUS_TOPIC, "topic": topic_for("mission_handler"), "action": "load_mission"},
        {"sender": NUS_TOPIC, "topic": topic_for("autopilot"), "action": "cmd"},
    ])


def _setup(tmp_path):
    os.environ["JOURNAL_FILE_PATH"] = str(tmp_path / "j.ndjson")
    bus = IntegrationBus()

    journal = JournalComponent(component_id="journal", bus=bus, topic=topic_for("journal"))
    autopilot = AutopilotComponent(component_id="autopilot", bus=bus, topic=topic_for("autopilot"))
    mission_handler = MissionHandlerComponent(component_id="mission_handler", bus=bus, topic=topic_for("mission_handler"))
    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies=_build_policies(),
    )

    bus.register_component(topic_for("journal"), journal)
    bus.register_component(topic_for("autopilot"), autopilot)
    bus.register_component(topic_for("mission_handler"), mission_handler)
    bus.register_component(topic_for("security_monitor"), sm)

    return bus, sm, autopilot, mission_handler, journal


def test_load_mission_e2e(tmp_path):
    bus, sm, autopilot, mission_handler, journal = _setup(tmp_path)

    msg = {
        "action": "proxy_request",
        "sender": NUS_TOPIC,
        "payload": {
            "target": {"topic": topic_for("mission_handler"), "action": "load_mission"},
            "data": {"wpl_content": WPL_SAMPLE, "mission_id": "m-e2e-01"},
        },
    }

    result = sm._handle_proxy_request(msg)
    assert result is not None
    resp = result.get("target_response", {})
    assert resp.get("ok") is True

    assert autopilot._state == "MISSION_LOADED"
    assert autopilot._mission is not None
    assert autopilot._mission["mission_id"] == "m-e2e-01"


def test_start_mission_no_external(tmp_path):
    """START without ORVD/Droneport topics should succeed (topics are empty)."""
    os.environ.pop("ORVD_TOPIC", None)
    os.environ.pop("DRONEPORT_TOPIC", None)

    bus, sm, autopilot, mission_handler, journal = _setup(tmp_path)

    load_msg = {
        "action": "proxy_request",
        "sender": NUS_TOPIC,
        "payload": {
            "target": {"topic": topic_for("mission_handler"), "action": "load_mission"},
            "data": {"wpl_content": WPL_SAMPLE, "mission_id": "m-start-01"},
        },
    }
    sm._handle_proxy_request(load_msg)

    cmd_msg = {
        "action": "proxy_request",
        "sender": NUS_TOPIC,
        "payload": {
            "target": {"topic": topic_for("autopilot"), "action": "cmd"},
            "data": {"command": "START"},
        },
    }
    result = sm._handle_proxy_request(cmd_msg)
    assert result is not None
    resp = result.get("target_response", {})
    assert resp.get("ok") is True
    assert autopilot._state == "EXECUTING"

    os.environ["ORVD_TOPIC"] = "v1.ORVD.ORVD001.main"
    os.environ["DRONEPORT_TOPIC"] = "v1.Droneport.DP001.main"


def test_start_mission_orvd_denied(tmp_path):
    """If ORVD denies departure, start should fail."""
    os.environ["ORVD_TOPIC"] = "v1.ORVD.ORVD001.main"

    bus, sm, autopilot, mission_handler, journal = _setup(tmp_path)

    sm._policies.add((topic_for("autopilot"), os.environ["ORVD_TOPIC"], "request_takeoff"))

    bus.register_topic_handler(os.environ["ORVD_TOPIC"], lambda msg: {"approved": False, "reason": "restricted"})
    bus.register_topic_handler(os.environ.get("NUS_TOPIC", ""), lambda msg: {"ok": True})

    load_msg = {
        "action": "proxy_request",
        "sender": NUS_TOPIC,
        "payload": {
            "target": {"topic": topic_for("mission_handler"), "action": "load_mission"},
            "data": {"wpl_content": WPL_SAMPLE, "mission_id": "m-denied-01"},
        },
    }
    sm._handle_proxy_request(load_msg)

    cmd_msg = {
        "action": "proxy_request",
        "sender": NUS_TOPIC,
        "payload": {
            "target": {"topic": topic_for("autopilot"), "action": "cmd"},
            "data": {"command": "START"},
        },
    }
    result = sm._handle_proxy_request(cmd_msg)
    resp = result.get("target_response", {}) if result else {}
    assert resp.get("ok") is False
    assert "orvd" in resp.get("error", "").lower()
