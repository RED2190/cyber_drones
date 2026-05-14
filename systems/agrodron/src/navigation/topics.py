"""Топики и actions для компонента навигации.

Топики строятся динамически (см. config.py и SYSTEM_NAME).
"""


class ComponentTopics:
    @staticmethod
    def navigation() -> str:
        from systems.agrodron.src.navigation.config import component_topic
        return component_topic()

    @staticmethod
    def sitl_adapter() -> str:
        from systems.agrodron.src.navigation.config import sitl_topic
        return sitl_topic()


class NavigationActions:
    """Actions, которые навигация публикует/обрабатывает через брокер."""

    # Публикация / приём навигационного состояния
    NAV_STATE = "nav_state"

    # Приём обновлённой конфигурации (min_satellites, max_hdop, publish_rate_hz и т.п.)
    UPDATE_CONFIG = "update_config"

    # Запрос текущего состояния навигации
    GET_STATE = "get_state"

