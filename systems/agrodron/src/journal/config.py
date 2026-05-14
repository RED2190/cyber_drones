"""Конфигурация компонента journal.

Чтение SYSTEM_NAME, топиков и параметров через переменные окружения.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from systems.agrodron.src.topic_utils import topic_for


def _journal_component_dir() -> Path:
    """Каталог пакета ``components/journal`` (рядом с этим ``config.py``)."""
    return Path(__file__).resolve().parent


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("journal")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def journal_file_path() -> str:
    """Путь к NDJSON-файлу для текущего запуска процесса.

    Приоритет:
    1. ``JOURNAL_FILE_PATH`` — один явный файл (режим как раньше).
    2. Иначе каталог ``JOURNAL_LOG_DIR``, либо ``<компонент>/system_journal/``,
       и новый файл ``system_<UTC>.ndjson`` на каждый запуск.
    """
    explicit = (os.environ.get("JOURNAL_FILE_PATH") or "").strip()
    if explicit:
        return explicit

    log_dir_raw = (os.environ.get("JOURNAL_LOG_DIR") or "").strip()
    if log_dir_raw:
        log_dir = Path(log_dir_raw)
    else:
        log_dir = _journal_component_dir() / "system_journal"

    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
    return str(log_dir / f"system_{ts}.ndjson")
