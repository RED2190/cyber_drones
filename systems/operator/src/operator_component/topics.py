"""Топики и actions для компонента Operator."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    OPERATOR_COMPONENT = f"{_P}components.operator"

    @classmethod
    def all(cls) -> list:
        return [cls.OPERATOR_COMPONENT]


class ExternalTopics:
    """Топики внешних систем."""
    INSURER = f"{_P}systems.insurer"
    ORVD = f"{_P}systems.orvd_system"
    REGULATOR = f"{_P}systems.regulator"
    AGREGATOR_REQUESTS = f"{_P}components.agregator.operator.requests"
    AGREGATOR_RESPONSES = f"{_P}components.agregator.operator.responses"
    # Основной Kafka-топик агрегатора. Публикация create_order сюда с correlation_id=order_id
    # заставляет Агрегатор перевести заказ из 'pending' в 'searching' (через его Kafka-консьюмер),
    # после чего SetOperatorOffer принимает нашу price_offer.
    AGREGATOR_SYSTEM = f"{_P}systems.agregator"
    # GCS drone_manager канал: при task.assign GCS публикует туда mission.upload
    # с готовым mission_id, drone_id и WPL. Operator подписан, чтобы
    # автоматически регистрировать и авторизовать миссию в ORVD под тем же
    # mission_id, который потом autopilot предъявляет в request_takeoff.
    GCS_DRONE_MANAGER = f"{_P}gcs.components.drone_manager"


class OperatorActions:
    REGISTER_DRONE = "register_drone"
    REQUEST_AVAILABLE_DRONES = "request_available_drones"
    SELECT_DRONE_AND_SEND_TO_AGGREGATOR = "select_drone_and_send_to_aggregator"
    BUY_INSURANCE_POLICY = "buy_insurance_policy"
    REGISTER_DRONE_IN_ORVD = "register_drone_in_orvd"
    SEND_ORDER_TO_NUS = "send_order_to_nus"
    CREATE_ORDER = "create_order"
    CONFIRM_PRICE = "confirm_price"

