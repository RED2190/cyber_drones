from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus

from components.journal import config


class JournalComponent(BaseComponent):
    """
    Компонент журнала агродрона.

    Принимает события на своём топике (только от монитора безопасности)
    и дописывает их в неизменяемый NDJSON-файл.
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

        super().__init__(
            component_id=component_id,
            component_type="journal",
            topic=topic,
            bus=bus,
        )

    # ------------------------------------------------------------ registration

    def _register_handlers(self) -> None:
        self.register_handler("LOG_EVENT", self._handle_log_event)

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        """Принимаем сообщения только от монитора безопасности."""
        sender = message.get("sender")
        return isinstance(sender, str) and sender.startswith("security_monitor")

    # ---------------------------------------------------------------- handlers

    def _handle_log_event(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обработчик записи события в журнал."""
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_payload"}

        source_component = str(payload.get("source") or message.get("sender") or "")
        event = payload.get("event") or "UNKNOWN"

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_component": source_component,
            "source_action": "LOG_EVENT",
            "event": event,
            "payload": payload,
        }

        try:
            line = json.dumps(record, ensure_ascii=False)
        except TypeError as exc:
            # Если payload не сериализуем, пишем минимальную информацию.
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
