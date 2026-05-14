"""Топики и actions для компонента журнала.

Топики строятся динамически (см. config.py и SYSTEM_NAME).
"""


class ComponentTopics:
    @staticmethod
    def journal() -> str:
        from systems.agrodron.src.journal.config import component_topic
        return component_topic()


class JournalActions:
    """Actions, которые журнал обрабатывает через брокер."""

    LOG_EVENT = "log_event"

