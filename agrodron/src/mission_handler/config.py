"""Конфигурация компонента mission_handler.

Чтение SYSTEM_NAME, топиков и параметров через переменные окружения.
"""
import os
from typing import Optional


def system_name() -> str:
    return (os.environ.get("SYSTEM_NAME") or "components").strip()


def topic_for(component_name: str) -> str:
    return f"{system_name()}.{component_name}"


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("mission_handler")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def autopilot_topic() -> str:
    return (os.environ.get("AUTOPILOT_TOPIC") or topic_for("autopilot")).strip()


def journal_topic() -> str:
    return (os.environ.get("JOURNAL_TOPIC") or topic_for("journal")).strip()


def sitl_kafka_servers() -> str:
    return (os.environ.get("SITL_KAFKA_SERVERS") or os.environ.get("KAFKA_BOOTSTRAP_SERVERS") or "localhost:9092").strip()


def sitl_kafka_home_topic() -> str:
    return (os.environ.get("SITL_KAFKA_HOME_TOPIC") or "sitl-drone-home").strip()


def sitl_drone_id() -> str:
    """Идентификатор дрона для SITL."""
    return (os.environ.get("SITL_DRONE_ID") or "drone_001").strip()


def _get_float(name: str, default: float, *, min_value: Optional[float] = None) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def mission_handler_request_timeout_s() -> float:
    return _get_float("MISSION_HANDLER_REQUEST_TIMEOUT_S", 10.0, min_value=0.1)
