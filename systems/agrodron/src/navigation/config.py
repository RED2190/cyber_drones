"""Конфигурация компонента navigation.

Чтение SYSTEM_NAME, топиков и параметров через переменные окружения.
SITL опрашивается по шине (request к топику SITL-адаптера через МБ).
"""
import os
from typing import Optional

from systems.agrodron.src.topic_utils import instance_id, topic_for


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("navigation")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def sitl_topic() -> str:
    """Топик SITL (цифровой двойник) для запросов навигации через МБ proxy_request."""
    return (os.environ.get("SITL_TOPIC") or "").strip()


def sitl_telemetry_request_topic() -> str:
    """Топик SITL для запроса телеметрии/навигации (SITL без action)."""
    return (os.environ.get("SITL_TELEMETRY_REQUEST_TOPIC") or sitl_topic()).strip()


def sitl_drone_id() -> str:
    return instance_id()


def journal_topic() -> str:
    return (os.environ.get("JOURNAL_TOPIC") or topic_for("journal")).strip()


def agrodron_nav_state_topic() -> str:
    """Топик для публикации NAV_STATE (опциональный broadcast для телеметрии)."""
    return (os.environ.get("AGRODRON_NAV_STATE_TOPIC") or f"{topic_for('navigation')}.state").strip()


def _get_float(name: str, default: float, *, min_value: Optional[float] = None) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def navigation_poll_interval_s() -> float:
    """Период опроса SITL через request (сек). 0.1 = 10 Гц."""
    return _get_float("NAVIGATION_POLL_INTERVAL_S", 0.1, min_value=0.05)


def navigation_request_timeout_s() -> float:
    """Таймаут request к SITL-адаптеру через МБ."""
    return _get_float("NAVIGATION_REQUEST_TIMEOUT_S", 1.0, min_value=0.1)
