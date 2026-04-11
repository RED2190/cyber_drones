"""Топики и actions для ORVD компонента."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    # Основной топик компонента ОрВД - все действия приходят сюда
    ORVD_COMPONENT = f"{_P}components.orvd_component"

    @classmethod
    def all(cls) -> list:
        return [cls.ORVD_COMPONENT]


class OrvdActions:
    # Эксплуатант
    REGISTER_DRONE = "register_drone"        # регистрирует дрона
    REGISTER_MISSION = "register_mission"    # регистрирует миссию

    # Дрон
    REQUEST_TAKEOFF = "request_takeoff"      # запрос на взлёт
    REVOKE_TAKEOFF = "revoke_takeoff"        # отзыв разрешения на полёт
    SEND_TELEMETRY = "send_telemetry"        # отправка телеметрии
    REQUEST_TELEMETRY = "request_telemetry"  # запрос телеметрии

     # ОрВД / система
    AUTHORIZE_MISSION = "authorize_mission"  # авторизация миссии
    GET_HISTORY = "get_history"              # получение истории событий

    # Зоны
    ADD_NO_FLY_ZONE = "add_no_fly_zone"      # добавление бесполётной зоны
    REMOVE_NO_FLY_ZONE = "remove_no_fly_zone" # удаление бесполётной зоны