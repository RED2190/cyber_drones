"""
Reusable journal component that collects log_event messages from the bus
and forwards them to the DroneAnalytics REST API (POST /log/event).

Environment variables:
    ANALYTICS_URL          -- DroneAnalytics backend URL (e.g. http://analytics-backend:8080)
    ANALYTICS_API_KEY      -- X-API-Key for POST /log/* endpoints
    ANALYTICS_SERVICE_NAME -- DroneAnalytics service enum value
    ANALYTICS_SERVICE_ID   -- integer service instance id (default: 1)
    JOURNAL_FLUSH_INTERVAL -- seconds between batch flushes (default: 2)
    JOURNAL_BATCH_SIZE     -- max events per HTTP request (default: 50)
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests as http_requests

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus


class AnalyticsJournalComponent(BaseComponent):
    """Subscribes to a journal topic, batches events, flushes to DroneAnalytics."""

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str,
        analytics_url: Optional[str] = None,
        api_key: Optional[str] = None,
        service_name: Optional[str] = None,
        service_id: Optional[int] = None,
    ):
        self._analytics_url = (
            analytics_url or os.environ.get("ANALYTICS_URL", "")
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("ANALYTICS_API_KEY", "")
        self._service_name = service_name or os.environ.get(
            "ANALYTICS_SERVICE_NAME", "aggregator"
        )
        self._service_id = service_id or int(
            os.environ.get("ANALYTICS_SERVICE_ID", "1")
        )
        self._flush_interval = float(
            os.environ.get("JOURNAL_FLUSH_INTERVAL", "2")
        )
        self._batch_size = int(os.environ.get("JOURNAL_BATCH_SIZE", "50"))

        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._flush_thread: Optional[threading.Thread] = None

        super().__init__(
            component_id=component_id,
            component_type="analytics_journal",
            topic=topic,
            bus=bus,
        )

    def _register_handlers(self) -> None:
        self.register_handler("log_event", self._handle_log_event)

    def _handle_log_event(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = message.get("payload", {})
        event_action = payload.get("event", "unknown")
        sender = payload.get("sender", message.get("sender", ""))
        success = payload.get("success", True)
        error = payload.get("error", "")
        component_id = payload.get("component_id", "")

        severity = "info" if success else "error"
        parts = [f"action={event_action}"]
        if sender:
            parts.append(f"sender={sender}")
        if component_id:
            parts.append(f"component={component_id}")
        parts.append(f"success={success}")
        if error:
            parts.append(f"error={error}")
        msg_text = ", ".join(parts)
        if len(msg_text) > 1024:
            msg_text = msg_text[:1021] + "..."

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        entry = {
            "apiVersion": "1.0.0",
            "timestamp": now_ms,
            "event_type": "event",
            "service": self._service_name,
            "service_id": self._service_id,
            "severity": severity,
            "message": msg_text,
        }

        batch = None
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._batch_size:
                batch = self._buffer[:]
                self._buffer.clear()

        if batch:
            self._send_batch(batch)

        return {"ok": True}

    def _flush_loop(self) -> None:
        while self._running:
            time.sleep(self._flush_interval)
            self._flush()

    def _flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()
        self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]) -> None:
        if not self._analytics_url or not batch:
            return
        url = f"{self._analytics_url}/log/event"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        try:
            resp = http_requests.post(url, json=batch, headers=headers, timeout=5)
            if resp.status_code >= 300:
                print(
                    f"[{self.component_id}] DroneAnalytics returned {resp.status_code}: "
                    f"{resp.text[:200]}"
                )
        except Exception as exc:
            print(f"[{self.component_id}] Failed to send to DroneAnalytics: {exc}")

    def start(self) -> None:
        super().start()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name=f"{self.component_id}-flush"
        )
        self._flush_thread.start()
        print(f"[{self.component_id}] Journal forwarding to {self._analytics_url}")

    def stop(self) -> None:
        self._flush()
        super().stop()
