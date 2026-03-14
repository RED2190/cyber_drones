"""Топики и actions для компонента обработчика миссий.

Топики строятся динамически (см. config.py и SYSTEM_NAME).
"""


class ComponentTopics:
    @staticmethod
    def mission_handler() -> str:
        from components.mission_handler.config import component_topic
        return component_topic()


class MissionHandlerActions:
    """Actions, которые обработчик миссий обрабатывает через брокер."""

    LOAD_MISSION = "LOAD_MISSION"
    VALIDATE_ONLY = "VALIDATE_ONLY"
    GET_STATE = "get_state"

