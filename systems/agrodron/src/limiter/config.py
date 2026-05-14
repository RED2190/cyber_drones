import os
from typing import Optional

from systems.agrodron.src.topic_utils import topic_for, system_name


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("limiter")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def journal_topic() -> str:
    return (os.environ.get("JOURNAL_TOPIC") or topic_for("journal")).strip()


def _get_float(name: str, default: float, *, min_value: Optional[float] = None) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def limiter_control_interval_s() -> float:
    return _get_float("LIMITER_CONTROL_INTERVAL_S", 0.5, min_value=0.01)


def limiter_nav_poll_interval_s() -> float:
    return _get_float("LIMITER_NAV_POLL_INTERVAL_S", 0.5, min_value=0.01)


def limiter_telemetry_poll_interval_s() -> float:
    return _get_float("LIMITER_TELEMETRY_POLL_INTERVAL_S", 1.0, min_value=0.01)


def limiter_request_timeout_s() -> float:
    return _get_float("LIMITER_REQUEST_TIMEOUT_S", 2.0, min_value=0.1)


def limiter_max_distance_from_path_m() -> float:
    return _get_float("LIMITER_MAX_DISTANCE_FROM_PATH_M", 10.0, min_value=0.0)


def limiter_max_alt_deviation_m() -> float:
    return _get_float("LIMITER_MAX_ALT_DEVIATION_M", 3.0, min_value=0.0)


def navigation_get_state_action() -> str:
    return (os.environ.get("LIMITER_NAVIGATION_GET_STATE_ACTION") or "get_state").strip()


def telemetry_get_state_action() -> str:
    return (os.environ.get("LIMITER_TELEMETRY_GET_STATE_ACTION") or "get_state").strip()

