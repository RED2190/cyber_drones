"""Топики и actions для компонента обработчика миссий.

Топики строятся динамически (см. config.py и SYSTEM_NAME).
"""


class ComponentTopics:
    @staticmethod
    def mission_handler() -> str:
        from systems.agrodron.src.mission_handler.config import component_topic
        return component_topic()


class MissionHandlerActions:
    """Actions, которые обработчик миссий обрабатывает через брокер."""

    LOAD_MISSION = "load_mission"
    VALIDATE_ONLY = "validate_only"
    GET_STATE = "get_state"

