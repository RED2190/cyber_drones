"""Конфигурация компонента telemetry.

Чтение топиков и параметров через переменные окружения.
"""
import os
from typing import Optional

from systems.agrodron.src.topic_utils import topic_for, system_name


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("telemetry")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def motors_topic() -> str:
    return (os.environ.get("MOTORS_TOPIC") or topic_for("motors")).strip()


def sprayer_topic() -> str:
    return (os.environ.get("SPRAYER_TOPIC") or topic_for("sprayer")).strip()


def navigation_topic() -> str:
    return (os.environ.get("NAVIGATION_TOPIC") or topic_for("navigation")).strip()


def motors_get_state_action() -> str:
    return (os.environ.get("MOTORS_GET_STATE_ACTION") or "get_state").strip()


def sprayer_get_state_action() -> str:
    return (os.environ.get("SPRAYER_GET_STATE_ACTION") or "get_state").strip()


def _get_float(name: str, default: float, *, min_value: Optional[float] = None) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def telemetry_poll_interval_s() -> float:
    return _get_float("TELEMETRY_POLL_INTERVAL_S", 0.5, min_value=0.05)


def telemetry_request_timeout_s() -> float:
    """Таймаут каждого proxy_request (motors / sprayer / navigation) через МБ.

    2 с часто мало при старте контейнеров и загруженном MQTT; без ответа-dict
    в журнале будет motors_ok=false. Рекомендуется 5–8 с, меньше таймаута МБ (10 с).
    """
    return _get_float("TELEMETRY_REQUEST_TIMEOUT_S", 6.0, min_value=0.1)
