import os
from pathlib import Path

from systems.agrodron.src.bus_mock import MockSystemBus
from systems.agrodron.src.journal import config
from systems.agrodron.src.journal.src.journal import JournalComponent

SM_TOPIC = config.security_monitor_topic()


def _make_component(tmp_path: str) -> JournalComponent:
    os.environ["JOURNAL_FILE_PATH"] = os.path.join(tmp_path, "journal_test.ndjson")
    bus = MockSystemBus()
    return JournalComponent(
        component_id="journal_test",
        bus=bus,
        topic=config.component_topic(),
    )


def _make_component_auto_log_dir(tmp_path: Path) -> JournalComponent:
    """Без JOURNAL_FILE_PATH: новый файл в JOURNAL_LOG_DIR."""
    bus = MockSystemBus()
    return JournalComponent(
        component_id="journal_auto",
        bus=bus,
        topic=config.component_topic(),
    )


def test_log_event_writes_to_file(tmp_path: str):
    comp = _make_component(str(tmp_path))

    msg = {
        "action": "log_event",
        "sender": SM_TOPIC,
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


def test_new_file_per_run_in_log_dir(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("JOURNAL_FILE_PATH", raising=False)
    monkeypatch.setenv("JOURNAL_LOG_DIR", str(tmp_path))
    comp = _make_component_auto_log_dir(tmp_path)
    journal_file = comp._journal_file_path
    assert journal_file.startswith(str(tmp_path))
    assert Path(journal_file).name.startswith("system_")
    assert journal_file.endswith(".ndjson")

    msg = {
        "action": "log_event",
        "sender": SM_TOPIC,
        "payload": {"event": "AUTO_DIR_EVENT", "source": "test"},
    }
    assert comp._handle_log_event(msg) == {"ok": True}

    with open(journal_file, "r", encoding="utf-8") as f:
        assert "AUTO_DIR_EVENT" in f.read()

