import os
import tempfile

from broker.system_bus import SystemBus
from components.journal import config
from components.journal.src.journal import JournalComponent


def _make_component(tmp_path: str) -> JournalComponent:
    os.environ["JOURNAL_FILE_PATH"] = os.path.join(tmp_path, "journal_test.ndjson")
    bus = SystemBus()
    return JournalComponent(
        component_id="journal_test",
        bus=bus,
        topic=config.component_topic(),
    )


def test_log_event_writes_to_file(tmp_path: str):
    comp = _make_component(str(tmp_path))

    msg = {
        "action": "LOG_EVENT",
        "sender": "security_monitor_test",
        "payload": {
            "event": "TEST_EVENT",
            "mission_id": "m1",
            "details": {"x": 1},
        },
    }

    result = comp._handle_log_event(msg)
    assert result and result["ok"]

    journal_file = os.environ["JOURNAL_FILE_PATH"]
    assert os.path.exists(journal_file)

    with open(journal_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 1
    assert "TEST_EVENT" in lines[0]

