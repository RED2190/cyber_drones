"""
Компонент навигации агродрона.

Читает данные SITL напрямую из Redis (SITL:{drone_id}),
нормализует в единый NAV_STATE, хранит и отдаёт по get_state.
"""
import json
import threading
import time
from typing import Any, Dict, Optional

from redis import Redis
from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus

from components.navigation import config
from components.navigation.src.sitl_normalizer import normalize_sitl_to_nav_state


class NavigationComponent(BaseComponent):
    """
    Компонент навигации агродрона.

    - Читает данные SITL из Redis (SITL:{drone_id}) с периодом 10 Гц;
    - Нормализует форматы SITL в NAV_STATE;
    - Хранит последнее состояние и отдаёт по get_state;
    - Принимает обновление конфигурации (nav_state, update_config).
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
        self._redis: Optional[Redis] = None

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
        return isinstance(sender, str) and sender.startswith("security_monitor")

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
        """Опрос Redis SITL (10 Гц)."""
        interval = config.navigation_poll_interval_s()
        while self._running:
            try:
                self._poll_sitl_once()
            except Exception as exc:
                print(f"[{self.component_id}] SITL poll error: {exc}")
            time.sleep(interval)

    def _read_sitl_from_redis(self, drone_id: str) -> Optional[Dict[str, Any]]:
        """Читает состояние дрона из Redis SITL:{drone_id}."""
        if self._redis is None:
            try:
                self._redis = Redis.from_url(config.sitl_redis_url(), decode_responses=True)
                self._redis.ping()
            except Exception:
                return None
        key = f"{config.sitl_redis_key_prefix()}:{drone_id}"
        try:
            raw = self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None

    def _poll_sitl_once(self) -> None:
        """Читает SITL из Redis, нормализует в NAV_STATE."""
        drone_id = self._config.get("drone_id") or config.sitl_drone_id()
        raw = self._read_sitl_from_redis(drone_id)
        if raw is None:
            return

        normalized = normalize_sitl_to_nav_state(raw, self._config)
        with self._lock:
            self._last_nav_state = normalized

        # Публикация в общий поток (для подписчиков, если есть)
        self._publish_nav_state(normalized)

        # Событие при деградации GPS
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
            "sender": self.component_id,
            "payload": {
                "target": {
                    "topic": config.journal_topic(),
                    "action": "LOG_EVENT",
                },
                "data": {
                    "event": "NAVIGATION_GPS_DEGRADED",
                    "source": "navigation",
                    "details": {"nav_state": nav_state},
                },
            },
        }
        self.bus.publish(config.security_monitor_topic(), msg)
