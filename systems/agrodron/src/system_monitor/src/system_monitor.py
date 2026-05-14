from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from broker.system_bus import SystemBus
from sdk.base_component import BaseComponent
from systems.agrodron.scripts.proxy_reply import unwrap_proxy_target_response

from systems.agrodron.src.system_monitor import config



class SystemMonitorComponent(BaseComponent):
    """
    Перехватывает сообщения топика журнала (те же log_event, что пишет journal)
    и периодически опрашивает телеметрию через security_monitor (proxy_request).
    """

    def __init__(self, component_id: str, bus: SystemBus, topic: str = ""):
        # Не self._journal_topic — поле занято BaseComponent (JOURNAL_TOPIC для авто-логов).
        self._journal_tap_topic = config.journal_topic()
        self._lock = threading.Lock()
        self._journal_events: Deque[Dict[str, Any]] = deque(maxlen=config.journal_buffer_max())
        self._last_telemetry: Optional[Dict[str, Any]] = None
        self._last_telemetry_ts: float = 0.0
        self._last_telemetry_error: Optional[str] = None
        self._last_telemetry_debug: Optional[str] = None

        self._poll_thread: Optional[threading.Thread] = None
        self._poll_interval_s = config.telemetry_poll_interval_s()
        self._request_timeout_s = config.telemetry_request_timeout_s()
        self._http_port = config.http_port()
        self._http_thread: Optional[threading.Thread] = None

        super().__init__(
            component_id=component_id,
            component_type="system_monitor",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    def _register_handlers(self) -> None:
        pass

    def start(self) -> None:
        super().start()
        ok = self.bus.subscribe(self._journal_tap_topic, self._on_journal_message)
        if not ok:
            print(f"[{self.component_id}] Warning: subscribe to journal topic failed")
        else:
            print(f"[{self.component_id}] Subscribed to journal tap: {self._journal_tap_topic}")

        self._poll_thread = threading.Thread(
            target=self._telemetry_poll_loop,
            name=f"{self.component_id}_telemetry_poll",
            daemon=True,
        )
        self._poll_thread.start()

        self._start_http_server()

    def stop(self) -> None:
        self.bus.unsubscribe(self._journal_tap_topic)
        super().stop()

    def _on_journal_message(self, message: Dict[str, Any]) -> None:
        if message.get("action") != "log_event":
            return
        entry = {
            "ts": time.time(),
            "action": message.get("action"),
            "sender": message.get("sender"),
            "payload": message.get("payload"),
        }
        with self._lock:
            self._journal_events.append(entry)

    def _telemetry_poll_loop(self) -> None:
        # Дождаться готовности telemetry / МБ после параллельного старта контейнеров
        time.sleep(1.5)
        while self._running:
            try:
                snap, dbg = self._fetch_telemetry()
                with self._lock:
                    self._last_telemetry_ts = time.time()
                    self._last_telemetry_debug = dbg
                    if snap is not None:
                        self._last_telemetry = snap
                        self._last_telemetry_error = None
                    else:
                        self._last_telemetry_error = (
                            "Не удалось получить снимок телеметрии (get_state). "
                            + (dbg or "См. telemetry_debug в /api/snapshot.")
                        )
            except Exception as exc:
                with self._lock:
                    self._last_telemetry_error = str(exc)
                print(f"[{self.component_id}] telemetry poll error: {exc}")
            time.sleep(self._poll_interval_s)

    @staticmethod
    def _extract_telemetry_snapshot(target_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ответ компонента telemetry на get_state — обычно в payload."""
        inner = target_response.get("payload")
        if isinstance(inner, dict):
            if any(k in inner for k in ("motors", "sprayer", "navigation", "last_poll_ts")):
                return inner
        if isinstance(target_response, dict) and any(
            k in target_response for k in ("motors", "sprayer", "navigation", "last_poll_ts")
        ):
            return target_response
        return None

    def _fetch_telemetry(self) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Возвращает (снимок, диагностика при неудаче)."""
        msg = {
            "action": "proxy_request",
            "sender": self.topic,
            "payload": {
                "target": {"topic": config.telemetry_topic(), "action": "get_state"},
                "data": {},
            },
        }
        sm_topic = config.security_monitor_topic()
        last_dbg: Optional[str] = None
        for attempt in range(3):
            t0 = time.monotonic()
            response = self.bus.request(
                sm_topic,
                msg,
                timeout=self._request_timeout_s,
            )
            elapsed = time.monotonic() - t0
            if not isinstance(response, dict):
                last_dbg = (
                    f"Попытка {attempt + 1}/3: ответ не dict (часто таймаут MQTT ~{elapsed:.1f}s при лимите {self._request_timeout_s}s). "
                    "На стороне МБ входящие сообщения обрабатываются пулом потоков: при нагрузке запрос мог не начать обработку до истечения таймаута. "
                    "Увеличьте MQTT_BUS_CALLBACK_WORKERS (по умолчанию 32) и/или SYSTEM_MONITOR_TELEMETRY_TIMEOUT_S (≥ таймаута МБ proxy, обычно 10s)."
                )
                time.sleep(0.3)
                continue
            outer_pl = response.get("payload")
            if isinstance(outer_pl, dict) and outer_pl.get("ok") is False:
                err = outer_pl.get("error", "proxy_failed")
                last_dbg = (
                    f"Попытка {attempt + 1}/3: МБ proxy_request: {err} "
                    f"(target={outer_pl.get('target_topic', '?')}). "
                    "Проверьте политики SECURITY_POLICIES и доступность telemetry."
                )
                time.sleep(0.3)
                continue
            target_response = unwrap_proxy_target_response(response)
            if not isinstance(target_response, dict):
                last_dbg = (
                    f"Попытка {attempt + 1}/3: не разобран ответ МБ (unwrap). Ключи корня: {list(response.keys())[:12]}"
                )
                time.sleep(0.3)
                continue
            snap = self._extract_telemetry_snapshot(target_response)
            if snap is not None:
                if snap.get("telemetry_trust_error"):
                    return None, (
                        f"Telemetry отклонила sender: ожидается топик МБ {snap.get('sender_expected')!r}, "
                        f"в запросе {snap.get('sender_received')!r}. Проверьте прокси МБ."
                    )
                return snap, None
            last_dbg = (
                f"Попытка {attempt + 1}/3: в ответе telemetry нет полей motors/sprayer/navigation. "
                f"Ключи target_response: {list(target_response.keys())[:12]}"
            )
            time.sleep(0.3)
        return None, last_dbg

    def _snapshot(self) -> Dict[str, Any]:
        with self._lock:
            events: List[Dict[str, Any]] = list(self._journal_events)
            return {
                "journal_events": events,
                "telemetry": self._last_telemetry,
                "telemetry_ts": self._last_telemetry_ts,
                "telemetry_error": self._last_telemetry_error,
                "telemetry_debug": self._last_telemetry_debug,
                "telemetry_request_timeout_s": self._request_timeout_s,
                "component_id": self.component_id,
                "journal_topic_tap": self._journal_tap_topic,
            }

    def _start_http_server(self) -> None:
        if not config.http_enabled():
            print(f"[{self.component_id}] HTTP disabled (SYSTEM_MONITOR_HTTP=0)")
            return
        try:
            from flask import Flask, jsonify, Response
        except ImportError:
            print(f"[{self.component_id}] Flask not installed, HTTP API disabled")
            return

        app = Flask(f"{self.component_id}_http")
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)

        @app.route("/health")
        def health():
            return jsonify({"status": "ok", "component": self.component_id})

        @app.route("/api/snapshot")
        def api_snapshot():
            return jsonify(self._snapshot())

        @app.route("/api/journal")
        def api_journal():
            with self._lock:
                return jsonify({"events": list(self._journal_events)})

        @app.route("/api/telemetry")
        def api_telemetry():
            with self._lock:
                return jsonify(
                    {
                        "snapshot": self._last_telemetry,
                        "ts": self._last_telemetry_ts,
                        "error": self._last_telemetry_error,
                    }
                )

        @app.route("/")
        def index():
            path = os.path.join(os.path.dirname(__file__), "dashboard_ru.html")
            try:
                with open(path, encoding="utf-8") as f:
                    html = f.read()
            except OSError:
                html = "<!DOCTYPE html><html><head><meta charset=utf-8><title>Монитор</title></head><body><p>Файл dashboard_ru.html не найден.</p></body></html>"
            return Response(html, mimetype="text/html; charset=utf-8")

        def run():
            app.run(host="0.0.0.0", port=self._http_port, threaded=True, use_reloader=False)

        self._http_thread = threading.Thread(target=run, daemon=True, name=f"{self.component_id}_http")
        self._http_thread.start()
        print(f"[{self.component_id}] HTTP UI http://0.0.0.0:{self._http_port}/")
