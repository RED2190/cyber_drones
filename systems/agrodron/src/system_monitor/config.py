"""Конфигурация system_monitor."""
from __future__ import annotations

import os
from typing import Optional

from systems.agrodron.src.topic_utils import topic_for


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("system_monitor")).strip()


def journal_topic() -> str:
    return (os.environ.get("JOURNAL_TOPIC") or topic_for("journal")).strip()


def telemetry_topic() -> str:
    return (os.environ.get("TELEMETRY_TOPIC") or topic_for("telemetry")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def _get_float(name: str, default: float, *, min_value: Optional[float] = None) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _get_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = int(default)
    else:
        value = int(raw)
    if value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def telemetry_poll_interval_s() -> float:
    return _get_float("SYSTEM_MONITOR_TELEMETRY_POLL_S", 1.0, min_value=0.1)


def telemetry_request_timeout_s() -> float:
    """Таймаут ответа от МБ на proxy_request до telemetry.

    Должен быть **не меньше**, чем SECURITY_MONITOR_PROXY_REQUEST_TIMEOUT_S (ожидание
    telemetry и её цепочки motors/sprayer/navigation внутри МБ), иначе внешний
    bus.request в system_monitor оборвётся раньше и снимок будет пустым.
    По умолчанию 15 с при типичном таймауте МБ 10 с.
    """
    return _get_float("SYSTEM_MONITOR_TELEMETRY_TIMEOUT_S", 15.0, min_value=0.1)


def journal_buffer_max() -> int:
    return _get_int("SYSTEM_MONITOR_JOURNAL_BUFFER", 2000, min_value=10)


def http_port() -> int:
    return _get_int("SYSTEM_MONITOR_HTTP_PORT", 8090, min_value=1)


def http_enabled() -> bool:
    raw = (os.environ.get("SYSTEM_MONITOR_HTTP") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")
