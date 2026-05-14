import os
from typing import Optional

from systems.agrodron.src.topic_utils import instance_id, topic_for, system_name


def component_topic() -> str:
    return (os.environ.get("COMPONENT_TOPIC") or topic_for("autopilot")).strip()


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


def autopilot_control_interval_s() -> float:
    return _get_float("AUTOPILOT_CONTROL_INTERVAL_S", 0.2, min_value=0.01)


def autopilot_nav_poll_interval_s() -> float:
    return _get_float("AUTOPILOT_NAV_POLL_INTERVAL_S", 0.2, min_value=0.01)


def autopilot_request_timeout_s() -> float:
    return _get_float("AUTOPILOT_REQUEST_TIMEOUT_S", 5.0, min_value=0.1)


def autopilot_start_mission_wait_s() -> float:
    return _get_float("AUTOPILOT_START_MISSION_WAIT_S", 3.0, min_value=0.0)


def navigation_get_state_action() -> str:
    return (os.environ.get("NAVIGATION_GET_STATE_ACTION") or "get_state").strip()


def orvd_topic() -> str:
    """Топик API ОрВД. Пусто = не обращаться к ОрВД."""
    return (os.environ.get("ORVD_TOPIC") or os.environ.get("ORVD_EXTERNAL_TOPIC") or "").strip()


def orvd_mock_success() -> bool:
    """Если True — не вызывать ОрВД по шине, считать разрешение на взлёт полученным (отладка / стенд без ОРВД)."""
    raw = (os.environ.get("AUTOPILOT_ORVD_MOCK_SUCCESS") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def orvd_drone_id() -> str:
    """Идентификатор дрона для ОрВД = INSTANCE_ID системы."""
    return instance_id()


def nus_topic() -> str:
    return (os.environ.get("NUS_TOPIC") or "").strip()


def droneport_topic() -> str:
    return (os.environ.get("DRONEPORT_TOPIC") or "").strip()


def droneport_mock_success() -> bool:
    """Если True — не вызывать Дронопорт по шине, считать ответы успешными (стенд без внешнего DronePort)."""
    raw = (os.environ.get("AUTOPILOT_DRONEPORT_MOCK_SUCCESS") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def droneport_drone_model() -> str:
    """Модель дрона для payload DronePort `request_landing` (поле `model`)."""
    return (os.environ.get("DRONEPORT_DRONE_MODEL") or "agrodron").strip()


def droneport_charging_battery_default() -> float:
    """Значение заряда (%) для `request_charging`, если в навигации нет поля battery."""
    return _get_float("DRONEPORT_CHARGING_BATTERY_DEFAULT", 50.0, min_value=0.0)


def droneport_landing_battery_default() -> float:
    """Значение заряда (%) в `request_landing`, если в навигации нет батареи."""
    return _get_float("DRONEPORT_LANDING_BATTERY_DEFAULT", 95.0, min_value=0.0)


def sitl_topic() -> str:
    return (os.environ.get("SITL_TOPIC") or "").strip()
