"""Топики и actions для Operator в составе dummy_fabric."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    OPERATOR = f"{_P}components.fabric_operator"


class OperatorActions:
    CONFIRM_ORDER = "confirm_order"
    START_ORDER = "start_order"
    FINISH_ORDER = "finish_order"
