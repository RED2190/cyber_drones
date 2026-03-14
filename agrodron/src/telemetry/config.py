import os
from typing import Optional


def system_name() -> str:
    return (os.environ.get("SYSTEM_NAME") or "components").strip()


def topic_for(component_name: str) -> str:
    return f"{system_name()}.{component_name}"


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("telemetry")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def motors_topic() -> str:
    return (os.environ.get("MOTORS_TOPIC") or topic_for("motors")).strip()


def sprayer_topic() -> str:
    return (os.environ.get("SPRAYER_TOPIC") or topic_for("sprayer")).strip()


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
    return _get_float("TELEMETRY_REQUEST_TIMEOUT_S", 2.0, min_value=0.1)

