"""Топики и actions для Gateway Operator."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    OPERATOR = f"{_P}systems.operator"


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


class GatewayActions:
    REGISTER_DRONE = "register_drone"
    REQUEST_AVAILABLE_DRONES = "request_available_drones"
    SELECT_DRONE_AND_SEND_TO_AGGREGATOR = "select_drone_and_send_to_aggregator"
    BUY_INSURANCE_POLICY = "buy_insurance_policy"
    REGISTER_DRONE_IN_ORVD = "register_drone_in_orvd"
    SEND_ORDER_TO_NUS = "send_order_to_nus"

