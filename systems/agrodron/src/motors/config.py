import os
from typing import Optional

from systems.agrodron.src.topic_utils import instance_id, topic_for


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("motors")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def sitl_mode() -> str:
    return (os.environ.get("SITL_MODE") or "mock").strip().lower()


def sitl_topic() -> str:
    return (os.environ.get("SITL_TOPIC") or "").strip()


def sitl_commands_topic() -> str:
    """Топик SITL для команд приводов (SITL без action)."""
    return (os.environ.get("SITL_COMMANDS_TOPIC") or sitl_topic()).strip()


def sitl_drone_id() -> str:
    return instance_id()


def _get_float(name: str, default: float, *, min_value: Optional[float] = None) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def motors_temperature_c_default() -> float:
    return _get_float("MOTORS_TEMPERATURE_C_DEFAULT", 55.0, min_value=-50.0)
