"""
Компонент навигации агродрона.

Запрашивает данные SITL через шину (proxy_request к SITL-адаптеру),
нормализует в единый NAV_STATE, хранит и отдаёт по get_state.
"""
import threading
import time
from typing import Any, Dict, Optional

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus
from systems.agrodron.scripts.proxy_reply import unwrap_proxy_target_response
from systems.agrodron.src.journal_log import publish_journal_event

from systems.agrodron.src.navigation import config
from systems.agrodron.src.navigation.src.sitl_normalizer import normalize_sitl_to_nav_state

class NavigationComponent(BaseComponent):
    """
    Компонент навигации агродрона.

    - Опрашивает SITL через request к топику SITL-адаптера (через МБ) с периодом 10 Гц;
    - Нормализует ответ (JSON) в NAV_STATE;
    - Хранит последнее состояние и отдаёт по get_state;
    - Принимает обновление конфигурации и ручную подстановку nav_state (nav_state, update_config).
    """

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str,
    ):
        self._last_nav_state: Optional[Dict[str, Any]] = None
        self._config: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._housekeeping_thread: Optional[threading.Thread] = None
        self._journal_logged_sitl_link = False

        super().__init__(
            component_id=component_id,
            component_type="navigation",
            topic=topic,
            bus=bus,
        )

    # ------------------------------------------------------------ registration

    def _register_handlers(self) -> None:
        self.register_handler("nav_state", self._handle_nav_state)
        self.register_handler("update_config", self._handle_update_config)
        self.register_handler("get_state", self._handle_get_state)

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        """Принимаем сообщения только от монитора безопасности."""
        sender = message.get("sender")
        return isinstance(sender, str) and sender == config.security_monitor_topic()

    # ---------------------------------------------------------------- handlers

    def _handle_nav_state(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_nav_payload"}

        normalized = normalize_sitl_to_nav_state(payload)
        with self._lock:
            self._last_nav_state = normalized
        return {"ok": True}

    def _handle_update_config(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_config_payload"}

        with self._lock:
            self._config.update(payload)
            current = dict(self._config)
        return {"ok": True, "config": current}

    def _handle_get_state(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        with self._lock:
            nav_state = dict(self._last_nav_state) if isinstance(self._last_nav_state, dict) else None
            config_copy = dict(self._config)
        # payload — для совместимости с autopilot/limiter (они читают target_response.payload)
        return {
            "nav_state": nav_state,
            "config": config_copy,
            "payload": nav_state,
        }

    # --------------------------------------------------------------- lifecycle

    def start(self) -> None:
        super().start()
        self._housekeeping_thread = threading.Thread(
            target=self._housekeeping_loop,
            name=f"{self.component_id}_housekeeping",
            daemon=True,
        )
        self._housekeeping_thread.start()

    def stop(self) -> None:
        super().stop()

    # ----------------------------------------------------------- housekeeping

    def _housekeeping_loop(self) -> None:
        """Периодический запрос к SITL через МБ (proxy_request)."""
        interval = config.navigation_poll_interval_s()
        while self._running:
            try:
                self._poll_sitl_once()
            except Exception as exc:
                # Suppress noisy poll logs; keep loop alive.
                _ = exc
            time.sleep(interval)

    def _request_sitl_state(self) -> Optional[Dict[str, Any]]:
        """Отправляет request к SITL-адаптеру через монитор безопасности, возвращает сырой JSON."""
        drone_id = self._config.get("drone_id") or config.sitl_drone_id()
        message = {
            "action": "proxy_request",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.sitl_telemetry_request_topic(),
                    "action": "request_position",
                },
                # Схема SITL: sitl-position-request.json — drone_id строка, pattern ^drone_[0-9]{3,4}$
                "data": {"drone_id": str(drone_id)} if drone_id else {},
            },
        }
        response = self.bus.request(
            config.security_monitor_topic(),
            message,
            timeout=config.navigation_request_timeout_s(),
        )
        target_response = unwrap_proxy_target_response(response)
        if not isinstance(target_response, dict):
            return None
        # RAW-reply от SITL: обычно это {lat, lon, alt, ...} + correlation_id.
        raw = target_response.get("payload") if isinstance(target_response.get("payload"), dict) else target_response
        if isinstance(raw, dict):
            # убираем служебные поля request/response, если SITL их эхо-включает
            raw = dict(raw)
            raw.pop("reply_to", None)
            raw.pop("correlation_id", None)
            return raw
        return None

    def _poll_sitl_once(self) -> None:
        """Запрашивает SITL через шину, нормализует в NAV_STATE."""
        raw = self._request_sitl_state()
        if raw is None:
            return

        normalized = normalize_sitl_to_nav_state(raw, self._config)
        with self._lock:
            self._last_nav_state = normalized

        self._publish_nav_state(normalized)

        if not self._journal_logged_sitl_link:
            self._journal_logged_sitl_link = True
            publish_journal_event(
                self.bus,
                self.topic,
                "NAVIGATION_SITL_LINK_OK",
                source="navigation",
                details={
                    "lat": normalized.get("lat"),
                    "lon": normalized.get("lon"),
                    "alt_m": normalized.get("alt_m"),
                    "sitl_request_topic": config.sitl_telemetry_request_topic(),
                },
            )
            publish_journal_event(
                self.bus,
                self.topic,
                "NAVIGATION_SITL_HOME_APPLIED",
                source="navigation",
                details={
                    "drone_id": self._config.get("drone_id") or config.sitl_drone_id(),
                    "lat": normalized.get("lat"),
                    "lon": normalized.get("lon"),
                    "alt_m": normalized.get("alt_m"),
                    "note": "Первый ответ SITL с координатами; состояние в Redis/двойнике доступно после цепочки set_home.",
                },
            )
        gps_valid = bool(normalized.get("gps_valid", True))
        if not gps_valid:
            self._log_gps_degraded(normalized)

    # ----------------------------------------------------------- publishing

    def _publish_nav_state(self, nav_state: Dict[str, Any]) -> None:
        """Публикует NAV_STATE в agrodron.navigation.state."""
        message = dict(nav_state)
        if not message.get("drone_id") and self._config.get("drone_id"):
            message["drone_id"] = self._config.get("drone_id")
        self.bus.publish(config.agrodron_nav_state_topic(), message)

    def _log_gps_degraded(self, nav_state: Dict[str, Any]) -> None:
        """Отправляет событие NAVIGATION_GPS_DEGRADED в журнал через МБ."""
        msg = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.journal_topic(),
                    "action": "log_event",
                },
                "data": {
                    "event": "NAVIGATION_GPS_DEGRADED",
                    "source": "navigation",
                    "details": {"nav_state": nav_state},
                },
            },
        }
        self.bus.publish(config.security_monitor_topic(), msg)
