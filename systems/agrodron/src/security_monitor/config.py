import os
from typing import Optional

from systems.agrodron.src.topic_utils import topic_for, system_name


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("security_monitor")).strip()


def _get_float(name: str, default: float, *, min_value: Optional[float] = None) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        value = float(raw)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def proxy_request_timeout_s() -> float:
    return _get_float("SECURITY_MONITOR_PROXY_REQUEST_TIMEOUT_S", 10.0, min_value=0.1)


def subscribe_warmup_s() -> float:
    return _get_float("SECURITY_MONITOR_SUBSCRIBE_WARMUP_S", 2.0, min_value=0.0)


def startup_probe_timeout_s() -> float:
    return _get_float("SECURITY_MONITOR_STARTUP_PROBE_TIMEOUT_S", 0.5, min_value=0.1)
