from __future__ import annotations

import time
from typing import Any, Dict, Optional

from broker.system_bus import SystemBus
from sdk.base_component import BaseComponent
from systems.agrodron.src.journal_log import publish_journal_event

from systems.agrodron.src.sprayer import config


class SprayerState:
    OFF = "OFF"
    ON = "ON"


class SprayerComponent(BaseComponent):
    """
    Компонент опрыскивателя.

    - Принимает SET_SPRAY (spray=true/false) только от security_monitor.
    - При изменении состояния пишет событие в journal через МБ.
    - Отдаёт текущее состояние по get_state (для telemetry).
    """

    def __init__(self, component_id: str, bus: SystemBus, topic: str = ""):
        self._state: str = SprayerState.OFF
        self._last_change_ts: float = time.time()
        self._temperature_c: float = config.sprayer_temperature_c_default()
        self._tank_level_pct: float = config.sprayer_tank_level_pct_default()

        super().__init__(
            component_id=component_id,
            component_type="sprayer",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        sender = message.get("sender")
        return isinstance(sender, str) and sender == config.security_monitor_topic()

    def _register_handlers(self) -> None:
        self.register_handler("set_spray", self._handle_set_spray)
        self.register_handler("get_state", self._handle_get_state)

    def _handle_set_spray(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_payload"}

        spray_flag = bool(payload.get("spray"))
        new_state = SprayerState.ON if spray_flag else SprayerState.OFF
        old_state = self._state

        if new_state != old_state:
            self._state = new_state
            self._last_change_ts = time.time()
            self._emit_sitl_command({"cmd": "SET_SPRAY", "spray": spray_flag})
            self._log_state_change(old_state, new_state)

        return {"ok": True, "state": self._state}

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "state": self._state,
            "last_change_ts": self._last_change_ts,
            "temperature_c": self._temperature_c,
            "tank_level_pct": self._tank_level_pct,
            "sitl_mode": config.sitl_mode(),
        }

    def _log_state_change(self, old_state: str, new_state: str) -> None:
        msg = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {"topic": config.journal_topic(), "action": "log_event"},
                "data": {
                    "event": "SPRAYER_STATE_CHANGED",
                    "source": "sprayer",
                    "details": {"old_state": old_state, "new_state": new_state},
                },
            },
        }
        self.bus.publish(config.security_monitor_topic(), msg)

    def _emit_sitl_command(self, command: Dict[str, Any]) -> None:
        mode = config.sitl_mode()
        sitl_topic = config.sitl_topic()
        publish_journal_event(
            self.bus,
            self.topic,
            "SPRAYER_SITL_OUT",
            source="sprayer",
            details={
                "sitl_mode": mode,
                "sitl_topic": sitl_topic or "",
                "command": command,
            },
        )
        if mode == "mock":
            self.bus.publish(sitl_topic, {"source": "sprayer", "command": command})
        else:
            self.bus.publish(
                sitl_topic,
                {
                    "source": "sprayer",
                    "command": command,
                    "note": f"sitl_mode={mode} not implemented, emitted as mock",
                },
            )

