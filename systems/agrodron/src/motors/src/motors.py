from __future__ import annotations

import math
import time
from typing import Any, Dict, Optional

from broker.system_bus import SystemBus
from sdk.base_component import BaseComponent
from systems.agrodron.src.journal_log import publish_journal_event

from systems.agrodron.src.motors import config

# Не чаще одной записи в журнал (веб-монитор) по обычным командам SITL
_SITL_JOURNAL_CMD_INTERVAL_S = 2.0

# Лимиты по схеме SITL (ARCHITECTURE.md): vx,vy [-50..50], vz [-10..10], mag_heading [0..359.9]
_VX_VY_MIN, _VX_VY_MAX = -50.0, 50.0
_VZ_MIN, _VZ_MAX = -10.0, 10.0
_MAG_HEADING_MIN, _MAG_HEADING_MAX = 0.0, 359.9


def _vx_vy_to_mag_heading(vx: float, vy: float) -> float:
    """Курс в градусах (0..360): North=0, East=90. При нулевой скорости — 0."""
    if abs(vx) < 1e-9 and abs(vy) < 1e-9:
        return 0.0
    heading_rad = math.atan2(vx, vy)
    return (math.degrees(heading_rad) + 360.0) % 360.0


class MotorsMode:
    IDLE = "IDLE"
    TRACKING = "TRACKING"
    LANDING = "LANDING"


class MotorsComponent(BaseComponent):
    """
    Компонент приводов (motors).

    Принимает команды:
    - SET_TARGET: целевые heading/speed/alt
    - LAND: аварийная посадка
    - get_state: вернуть последнее состояние

    Все входящие команды принимаются только от security_monitor (trusted sender).
    """

    def __init__(self, component_id: str, bus: SystemBus, topic: str = ""):
        self._mode: str = MotorsMode.IDLE
        self._last_target: Optional[Dict[str, Any]] = None
        self._last_cmd_ts: float = 0.0
        self._temperature_c: float = config.motors_temperature_c_default()
        self._last_sitl_journal_ts: float = 0.0

        super().__init__(
            component_id=component_id,
            component_type="motors",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        sender = message.get("sender")
        return isinstance(sender, str) and sender == config.security_monitor_topic()

    def _register_handlers(self) -> None:
        self.register_handler("set_target", self._handle_set_target)
        self.register_handler("land", self._handle_land)
        self.register_handler("get_state", self._handle_get_state)

    def start(self) -> None:
        super().start()
        publish_journal_event(
            self.bus,
            self.topic,
            "MOTORS_SITL_READY",
            source="motors",
            details={
                "sitl_mode": config.sitl_mode(),
                "sitl_commands_topic": config.sitl_commands_topic(),
                "drone_id": config.sitl_drone_id(),
            },
        )

    def _handle_set_target(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_payload"}

        # Поддержка нового формата (vx, vy, vz) и старого (heading_deg, ground_speed_mps)
        vx = payload.get("vx")
        vy = payload.get("vy")
        vz = payload.get("vz")
        if vx is None or vy is None or vz is None:
            h = float(payload.get("heading_deg") or 0.0)
            s = float(payload.get("ground_speed_mps") or 0.0)
            hr = math.radians(h)
            vx = s * math.sin(hr)
            vy = s * math.cos(hr)
            vz = 0.0
        else:
            vx = float(vx)
            vy = float(vy)
            vz = float(vz)

        target = {
            "vx": vx,
            "vy": vy,
            "vz": vz,
            "alt_m": payload.get("alt_m"),
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "heading_deg": payload.get("heading_deg"),
            "drop": payload.get("drop", False),
        }
        self._last_target = target
        self._mode = MotorsMode.TRACKING
        self._last_cmd_ts = time.time()

        self._emit_sitl_command(target, reason="set_target")
        return {"ok": True, "mode": self._mode}

    def _handle_land(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None
        self._mode = MotorsMode.LANDING
        self._last_cmd_ts = time.time()
        # Аварийная посадка: нулевая скорость, emergency_landing=True
        last = self._last_target or {}
        self._emit_sitl_command(
            {
                "vx": 0.0, "vy": 0.0, "vz": -2.0,
                "alt_m": last.get("alt_m", 0.0),
                "lat": last.get("lat", 0.0),
                "lon": last.get("lon", 0.0),
                "heading_deg": last.get("heading_deg", 0.0),
                "drop": False,
                "emergency_landing": True,
            },
            reason="land",
        )
        return {"ok": True, "mode": self._mode}

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "mode": self._mode,
            "last_target": self._last_target,
            "last_cmd_ts": self._last_cmd_ts,
            "temperature_c": self._temperature_c,
            "sitl_mode": config.sitl_mode(),
        }

    def _build_sitl_command(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Формирует команду в формате SITL (ARCHITECTURE.md): sitl/commands.
        Обязательные поля: drone_id, vx, vy, vz, mag_heading.
        """
        vx = max(_VX_VY_MIN, min(_VX_VY_MAX, float(data.get("vx") or 0.0)))
        vy = max(_VX_VY_MIN, min(_VX_VY_MAX, float(data.get("vy") or 0.0)))
        vz = max(_VZ_MIN, min(_VZ_MAX, float(data.get("vz") or 0.0)))
        heading_deg = data.get("heading_deg")
        if heading_deg is not None:
            mag_heading = max(
                _MAG_HEADING_MIN,
                min(_MAG_HEADING_MAX, (float(heading_deg) % 360.0)),
            )
        else:
            mag_heading = max(
                _MAG_HEADING_MIN,
                min(_MAG_HEADING_MAX, round(_vx_vy_to_mag_heading(vx, vy), 1)),
            )

        return {
            "drone_id": config.sitl_drone_id(),
            "vx": round(vx, 2),
            "vy": round(vy, 2),
            "vz": round(vz, 2),
            "mag_heading": round(mag_heading, 1),
        }

    def _emit_sitl_command(self, command: Dict[str, Any], *, reason: str = "command") -> None:
        """
        Публикует команду в SITL через монитор безопасности (proxy_publish).
        Топик и брокер задаются в ENV (SITL_COMMANDS_TOPIC, брокер системы).
        """
        sitl_msg = self._build_sitl_command(command)
        message = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.sitl_commands_topic(),
                    "action": "__raw__",
                },
                "data": sitl_msg,
            },
        }
        self.bus.publish(config.security_monitor_topic(), message)
        self._journal_sitl_command(
            sitl_msg,
            reason=reason,
            emergency=bool(command.get("emergency_landing")),
        )

    def _journal_sitl_command(
        self,
        sitl_msg: Dict[str, Any],
        *,
        reason: str,
        emergency: bool,
    ) -> None:
        """Запись в журнал для веб-монитора: посадка/авария — всегда; set_target — не чаще раз в интервал."""
        now = time.monotonic()
        force = emergency or reason == "land"
        if not force and now - self._last_sitl_journal_ts < _SITL_JOURNAL_CMD_INTERVAL_S:
            return
        if not force:
            self._last_sitl_journal_ts = now
        event = "SITL_MOTORS_LAND_CMD" if force else "SITL_MOTORS_OUT"
        publish_journal_event(
            self.bus,
            self.topic,
            event,
            source="motors",
            details={
                "reason": reason,
                "sitl_commands_topic": config.sitl_commands_topic(),
                "drone_id": sitl_msg.get("drone_id"),
                "vx": sitl_msg.get("vx"),
                "vy": sitl_msg.get("vy"),
                "vz": sitl_msg.get("vz"),
                "mag_heading": sitl_msg.get("mag_heading"),
                "emergency": emergency,
            },
        )
