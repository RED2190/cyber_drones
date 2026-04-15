"""Integration tests: proxy_publish through security_monitor."""
import json
import os

from agrodron.tests.integration.integration_bus import IntegrationBus
from systems.agrodron.src.sdk.topic_utils import topic_for

from systems.agrodron.src.security_monitor.src.security_monitor import SecurityMonitorComponent
from systems.agrodron.src.journal.src.journal import JournalComponent


def _policies_json(policies):
    return json.dumps(policies)


def test_proxy_publish_allowed(tmp_path):
    os.environ["JOURNAL_FILE_PATH"] = str(tmp_path / "j.ndjson")
    bus = IntegrationBus()
    journal_topic = topic_for("journal")

    journal = JournalComponent(
        component_id="journal",
        bus=bus,
        topic=journal_topic,
    )

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies=_policies_json([
            {"sender": topic_for("autopilot"), "topic": journal_topic, "action": "log_event"},
        ]),
    )

    bus.register_component(journal_topic, journal)
    bus.register_component(topic_for("security_monitor"), sm)

    msg = {
        "action": "proxy_publish",
        "sender": topic_for("autopilot"),
        "payload": {
            "target": {"topic": journal_topic, "action": "log_event"},
            "data": {"event": "TEST_EVENT", "source": "autopilot"},
        },
    }

    result = sm._handle_proxy_publish(msg)
    assert result is not None
    assert result.get("published") is True

    journal_file = str(tmp_path / "j.ndjson")
    assert os.path.exists(journal_file)
    with open(journal_file) as f:
        lines = f.readlines()
    assert len(lines) >= 1
    assert "TEST_EVENT" in lines[0]


def test_proxy_publish_denied():
    bus = IntegrationBus()

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies="[]",
    )

    msg = {
        "action": "proxy_publish",
        "sender": "unknown_component",
        "payload": {
            "target": {"topic": topic_for("journal"), "action": "log_event"},
            "data": {"event": "SHOULD_NOT_APPEAR"},
        },
    }

    result = sm._handle_proxy_publish(msg)
    assert result is None
