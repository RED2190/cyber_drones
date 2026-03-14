import os
from typing import Optional


def system_name() -> str:
    return (os.environ.get("SYSTEM_NAME") or "components").strip()


def topic_for(component_name: str) -> str:
    return f"{system_name()}.{component_name}"


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("motors")).strip()


def security_monitor_topic() -> str:
    return (os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")).strip()


def sitl_mode() -> str:
    # mock | mqtt | redis | http (пока реализован mock)
    return (os.environ.get("SITL_MODE") or "mock").strip().lower()


def sitl_commands_topic() -> str:
    # Топик “наружу” для наблюдения за командами, когда SITL не подключен
    default = f"{system_name()}.sitl.commands"
    return (os.environ.get("SITL_COMMANDS_TOPIC") or default).strip()


def sitl_kafka_servers() -> str:
    return (os.environ.get("SITL_KAFKA_SERVERS") or os.environ.get("KAFKA_BOOTSTRAP_SERVERS") or "localhost:9092").strip()


def sitl_kafka_commands_topic() -> str:
    return (os.environ.get("SITL_KAFKA_COMMANDS_TOPIC") or "input-messages").strip()


def sitl_drone_id() -> str:
    """Идентификатор дрона для SITL (drone_001, drone_002 и т.д.)."""
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


def motors_temperature_c_default() -> float:
    return _get_float("MOTORS_TEMPERATURE_C_DEFAULT", 55.0, min_value=-50.0)

