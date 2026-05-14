import os
from typing import Optional

from systems.agrodron.src.topic_utils import topic_for, system_name


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("sprayer")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def journal_topic() -> str:
    return (os.environ.get("JOURNAL_TOPIC") or topic_for("journal")).strip()


def sitl_mode() -> str:
    return (os.environ.get("SITL_MODE") or "mock").strip().lower()


def sitl_topic() -> str:
    return (os.environ.get("SITL_TOPIC") or "").strip()


def _get_float(
    name: str,
    default: float,
    *,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")
    return value


def sprayer_temperature_c_default() -> float:
    return _get_float("SPRAYER_TEMPERATURE_C_DEFAULT", 40.0, min_value=-50.0)


def sprayer_tank_level_pct_default() -> float:
    return _get_float("SPRAYER_TANK_LEVEL_PCT_DEFAULT", 75.0, min_value=0.0, max_value=100.0)

