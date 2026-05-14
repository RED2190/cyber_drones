from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus

from systems.agrodron.src.journal import config


class JournalComponent(BaseComponent):
    """
    Компонент журнала агродрона.

    Принимает события на своём топике (только от монитора безопасности)
    и дописывает их в NDJSON-файл текущего запуска (по умолчанию новый файл
    в ``components/journal/system_journal/``).
    """

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str,
    ):
        self._journal_file_path = config.journal_file_path()
        self._lock = threading.Lock()

        journal_dir = os.path.dirname(self._journal_file_path)
        if journal_dir:
            os.makedirs(journal_dir, exist_ok=True)

        print(f"[{component_id}] Journal file: {self._journal_file_path}")

        super().__init__(
            component_id=component_id,
            component_type="journal",
            topic=topic,
            bus=bus,
        )

    # ------------------------------------------------------------ registration

    def _register_handlers(self) -> None:
        self.register_handler("log_event", self._handle_log_event)

    def start(self) -> None:
        super().start()
        self._append_local_record(
            "JOURNAL_SERVICE_READY",
            "journal",
            {"journal_file": self._journal_file_path},
        )

    # ------------------------------------------------------------------ utils

    def _append_local_record(self, event: str, source: str, details: Dict[str, Any]) -> None:
        """Прямая запись в NDJSON при старте сервиса (ещё нет доверенного сообщения от МБ)."""
        payload = {"event": event, "source": source, "details": details}
        self._persist_payload(payload, source_action="local_start")

    def _persist_payload(
        self,
        payload: Dict[str, Any],
        *,
        source_action: str = "log_event",
    ) -> Optional[Dict[str, Any]]:
        """Формирует запись и дописывает в файл (общая логика с log_event)."""
        source_component = str(payload.get("source") or "")
        event = payload.get("event") or "UNKNOWN"

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_component": source_component,
            "source_action": source_action,
            "event": event,
            "payload": payload,
        }

        try:
            line = json.dumps(record, ensure_ascii=False)
        except TypeError as exc:
            record["payload"] = {"error": f"non-serializable payload: {exc}"}
            line = json.dumps(record, ensure_ascii=False)

        with self._lock:
            try:
                with open(self._journal_file_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError as exc:
                print(f"[{self.component_id}] failed to write journal: {exc}")
                return {"ok": False, "error": "write_failed"}

        return {"ok": True}

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        """Принимаем сообщения только от монитора безопасности."""
        sender = message.get("sender")
        return isinstance(sender, str) and sender == config.security_monitor_topic()

    # ---------------------------------------------------------------- handlers

    def _handle_log_event(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обработчик записи события в журнал."""
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_payload"}

        return self._persist_payload(payload, source_action="log_event")
