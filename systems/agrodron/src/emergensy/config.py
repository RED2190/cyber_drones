import os
from typing import Optional

from systems.agrodron.src.topic_utils import topic_for, system_name


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("emergensy")).strip()


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


def emergensy_publish_timeout_s() -> float:
    # На текущей реализации publish() возвращает bool, таймаутов нет,
    # но параметр оставляем для унификации (под будущий брокер/адаптер).
    return _get_float("EMERGENSY_PUBLISH_TIMEOUT_S", 1.0, min_value=0.0)

