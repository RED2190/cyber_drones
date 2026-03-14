"""Конфигурация компонента navigation.

Чтение SYSTEM_NAME, топиков и параметров через переменные окружения.
"""
import os
from typing import Optional


def system_name() -> str:
    return (os.environ.get("SYSTEM_NAME") or "components").strip()


def topic_for(component_name: str) -> str:
    return f"{system_name()}.{component_name}"


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("navigation")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def sitl_adapter_topic() -> str:
    """Устаревшее: навигация читает Redis напрямую. Оставлено для совместимости."""
    return (os.environ.get("SITL_ADAPTER_TOPIC") or topic_for("sitl_adapter")).strip()


def sitl_redis_url() -> str:
    return (os.environ.get("SITL_REDIS_URL") or os.environ.get("REDIS_URL") or "redis://localhost:6379/0").strip()


def sitl_redis_key_prefix() -> str:
    return (os.environ.get("SITL_REDIS_KEY_PREFIX") or "SITL").strip()


def sitl_drone_id() -> str:
    return (os.environ.get("SITL_DRONE_ID") or "drone_001").strip()


def journal_topic() -> str:
    return (os.environ.get("JOURNAL_TOPIC") or topic_for("journal")).strip()


def agrodron_nav_state_topic() -> str:
    """Топик для публикации NAV_STATE (опциональный broadcast для телеметрии)."""
    default = f"{system_name()}.navigation.state"
    return (os.environ.get("AGRODRON_NAV_STATE_TOPIC") or default).strip()


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
    """Период опроса SITL (сек). 0.1 = 10 Гц."""
    return _get_float("NAVIGATION_POLL_INTERVAL_S", 0.1, min_value=0.05)


def navigation_request_timeout_s() -> float:
    """Таймаут запроса к SITL-адаптеру через МБ."""
    return _get_float("NAVIGATION_REQUEST_TIMEOUT_S", 1.0, min_value=0.1)
