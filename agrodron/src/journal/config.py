"""Конфигурация компонента journal.

Чтение SYSTEM_NAME, топиков и параметров через переменные окружения.
"""
import os


def system_name() -> str:
    return (os.environ.get("SYSTEM_NAME") or "components").strip()


def topic_for(component_name: str) -> str:
    return f"{system_name()}.{component_name}"


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("journal")).strip()


def journal_file_path() -> str:
    return (os.environ.get("JOURNAL_FILE_PATH") or "/data/agrodron_journal.ndjson").strip()
