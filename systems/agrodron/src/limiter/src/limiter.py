from typing import Any, Dict, Optional
import threading
import time

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus
from systems.agrodron.scripts.proxy_reply import extract_navigation_nav_state_from_target_response
from systems.agrodron.scripts.proxy_reply import unwrap_proxy_target_response

from systems.agrodron.src.limiter import config


class LimiterComponent(BaseComponent):
    """
    Упрощённый компонент ограничителя.

    Хранит миссию, последние навигационные и телеметрические данные, вычисляет
    грубое отклонение от маршрута и при превышении порогов публикует событие
    для экстренных ситуаций (через брокер/монитор).
    """

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str = "",
    ):
        self._mission: Optional[Dict[str, Any]] = None
        self._last_nav: Optional[Dict[str, Any]] = None
        self._last_telemetry: Optional[Dict[str, Any]] = None
        self._state: str = "NORMAL"
        self._max_distance_from_path_m: float = config.limiter_max_distance_from_path_m()
        self._max_alt_deviation_m: float = config.limiter_max_alt_deviation_m()

        self._control_thread: Optional[threading.Thread] = None
        self._control_interval_s: float = config.limiter_control_interval_s()
        self._nav_poll_interval_s: float = config.limiter_nav_poll_interval_s()
        self._telemetry_poll_interval_s: float = config.limiter_telemetry_poll_interval_s()
        self._request_timeout_s: float = config.limiter_request_timeout_s()
        self._last_nav_poll_ts: float = 0.0
        self._last_telemetry_poll_ts: float = 0.0

        super().__init__(
            component_id=component_id,
            component_type="limiter",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        sender = message.get("sender")
        return isinstance(sender, str) and sender == config.security_monitor_topic()

    # ------------------------------------------------------------ registration

    def _register_handlers(self) -> None:
        self.register_handler("mission_load", self._handle_mission_load)
        self.register_handler("nav_state", self._handle_nav_state)
        self.register_handler("update_config", self._handle_update_config)
        self.register_handler("get_state", self._handle_get_state)

    # --------------------------------------------------------------- lifecycle

    def start(self) -> None:
        super().start()
        self._control_thread = threading.Thread(
            target=self._control_loop,
            name=f"{self.component_id}_control",
            daemon=True,
        )
        self._control_thread.start()

    # ---------------------------------------------------------------- handlers

    def _handle_mission_load(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None
        payload = message.get("payload") or {}
        mission = payload.get("mission")
        if not isinstance(mission, dict):
            return {"ok": False, "error": "invalid_mission"}
        self._mission = mission
        return {"ok": True}

    def _handle_nav_state(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None
        payload = message.get("payload") or {}
        if isinstance(payload, dict):
            self._last_nav = payload
            self._recalculate()
        return {"ok": True}

    def _handle_update_config(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None
        payload = message.get("payload") or {}
        if "max_distance_from_path_m" in payload:
            self._max_distance_from_path_m = float(payload["max_distance_from_path_m"])
        if "max_alt_deviation_m" in payload:
            self._max_alt_deviation_m = float(payload["max_alt_deviation_m"])
        return {
            "ok": True,
            "max_distance_from_path_m": self._max_distance_from_path_m,
            "max_alt_deviation_m": self._max_alt_deviation_m,
        }

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "state": self._state,
            "max_distance_from_path_m": self._max_distance_from_path_m,
            "max_alt_deviation_m": self._max_alt_deviation_m,
        }

    # -------------------------------------------------------------- core logic

    def _control_loop(self) -> None:
        while self._running:
            try:
                self._poll_navigation_if_due()
                self._poll_telemetry_if_due()
                self._recalculate()
            except Exception as exc:
                print(f"[{self.component_id}] control loop error: {exc}")
            time.sleep(self._control_interval_s)

    def _poll_navigation_if_due(self) -> None:
        now = time.monotonic()
        if (now - self._last_nav_poll_ts) < self._nav_poll_interval_s:
            return
        self._last_nav_poll_ts = now

        message = {
            "action": "proxy_request",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.topic_for("navigation"),
                    "action": config.navigation_get_state_action(),
                },
                "data": {},
            },
        }
        response = self.bus.request(
            config.security_monitor_topic(),
            message,
            timeout=self._request_timeout_s,
        )
        target_response = unwrap_proxy_target_response(response)
        nav_state = extract_navigation_nav_state_from_target_response(target_response)
        if isinstance(nav_state, dict):
            self._last_nav = nav_state

    def _poll_telemetry_if_due(self) -> None:
        now = time.monotonic()
        if (now - self._last_telemetry_poll_ts) < self._telemetry_poll_interval_s:
            return
        self._last_telemetry_poll_ts = now

        message = {
            "action": "proxy_request",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.topic_for("telemetry"),
                    "action": config.telemetry_get_state_action(),
                },
                "data": {},
            },
        }
        response = self.bus.request(
            config.security_monitor_topic(),
            message,
            timeout=self._request_timeout_s,
        )
        target_response = unwrap_proxy_target_response(response)
        if not isinstance(target_response, dict):
            return
        telem_payload = target_response.get("payload")
        if isinstance(telem_payload, dict):
            self._last_telemetry = telem_payload

    def _recalculate(self) -> None:
        if not self._mission or not self._last_nav:
            return

        steps = self._mission.get("steps") or []
        if not steps:
            return

        target = steps[-1]
        try:
            lat = float(self._last_nav.get("lat"))
            lon = float(self._last_nav.get("lon"))
            alt = float(self._last_nav.get("alt_m"))
            t_lat = float(target.get("lat"))
            t_lon = float(target.get("lon"))
            t_alt = float(target.get("alt_m"))
        except (TypeError, ValueError):
            return

        # Очень грубая оценка расстояния: просто евклидова метрика в градусах,
        # умноженная на константу, достаточная для прототипа.
        d_lat = lat - t_lat
        d_lon = lon - t_lon
        distance_m = ((d_lat**2 + d_lon**2) ** 0.5) * 111_000.0
        alt_dev = abs(alt - t_alt)

        if distance_m > self._max_distance_from_path_m or alt_dev > self._max_alt_deviation_m:
            if self._state != "EMERGENCY":
                self._state = "EMERGENCY"
                self._publish_emergency(distance_m, alt_dev)
        elif distance_m > 0.5 * self._max_distance_from_path_m or alt_dev > 0.5 * self._max_alt_deviation_m:
            if self._state != "WARNING":
                self._log_to_journal("LIMITER_DEVIATION_WARNING", {"distance_m": distance_m, "alt_deviation_m": alt_dev})
            self._state = "WARNING"
        else:
            self._state = "NORMAL"

    def _publish_emergency(self, distance_m: float, alt_dev: float) -> None:
        details = {
            "distance_from_path_m": distance_m,
            "max_distance_from_path_m": self._max_distance_from_path_m,
            "alt_deviation_m": alt_dev,
            "max_alt_deviation_m": self._max_alt_deviation_m,
        }
        self._log_to_journal("LIMITER_EMERGENCY_LAND_REQUIRED", details)
        event_payload = {
            "event": "EMERGENCY_LAND_REQUIRED",
            "details": details,
        }
        # Нет подписок на чужие топики: доставляем событие в emergensy через МБ.
        message = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.topic_for("emergensy"),
                    "action": "limiter_event",
                },
                "data": event_payload,
            },
        }
        self.bus.publish(config.security_monitor_topic(), message)

    def _log_to_journal(self, event: str, details: Dict[str, Any]) -> None:
        """Отправка события в журнал через монитор безопасности."""
        msg = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {"topic": config.journal_topic(), "action": "log_event"},
                "data": {"event": event, "source": "limiter", "details": details},
            },
        }
        self.bus.publish(config.security_monitor_topic(), msg)

