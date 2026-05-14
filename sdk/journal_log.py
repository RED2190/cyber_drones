"""
Вспомогательная функция для публикации событий в журнал.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def publish_journal_event(
    bus: Any,
    sender_topic: str,
    event: str,
    *,
    source: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Публикует log_event в топик журнала."""
    journal_topic = os.environ.get("JOURNAL_TOPIC", "").strip()
    if not journal_topic:
        from sdk.topic_utils import topic_for
        journal_topic = topic_for("journal")

    msg = {
        "action": "log_event",
        "sender": sender_topic,
        "payload": {
            "event": event,
            "source": source or sender_topic,
            "details": details or {},
        },
    }
    try:
        bus.publish(journal_topic, msg)
    except Exception as exc:
        logger.debug("[journal_log] publish failed: %s", exc)
