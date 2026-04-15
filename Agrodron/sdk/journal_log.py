"""
Запись событий в компонент journal через security_monitor (proxy_publish → log_event).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from broker.system_bus import SystemBus
from sdk.topic_utils import topic_for

logger = logging.getLogger(__name__)


def publish_journal_event(
    bus: SystemBus,
    sender_topic: str,
    event: str,
    *,
    source: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Публикует событие в журнал. Требуется политика МБ: (sender_topic, journal, log_event).
    """
    msg = {
        "action": "proxy_publish",
        "sender": sender_topic,
        "payload": {
            "target": {"topic": topic_for("journal"), "action": "log_event"},
            "data": {
                "event": event,
                "source": source,
                "details": details or {},
            },
        },
    }
    try:
        bus.publish(topic_for("security_monitor"), msg)
    except Exception as exc:
        logger.debug("journal event %s not published: %s", event, exc)
