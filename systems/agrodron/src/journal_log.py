"""
Публикация событий в журнал через МБ (proxy_publish). Только для Agrodron.
"""
from __future__ import annotations

from typing import Any, Dict

from broker.system_bus import SystemBus

from systems.agrodron.src.topic_utils import topic_for


def publish_journal_event(
    bus: SystemBus,
    sender_topic: str,
    event: str,
    *,
    source: str,
    details: Dict[str, Any],
) -> None:
    sm = topic_for("security_monitor")
    journal = topic_for("journal")
    msg = {
        "action": "proxy_publish",
        "sender": sender_topic,
        "payload": {
            "target": {"topic": journal, "action": "log_event"},
            "data": {
                "event": event,
                "source": source,
                "details": details,
            },
        },
    }
    try:
        bus.publish(sm, msg)
    except Exception:
        pass
