"""Топики и actions для Insurer в составе dummy_fabric."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    INSURER = f"{_P}components.fabric_insurer"


class InsurerActions:
    CREATE_INSURANCE = "create_insurance"
    READ_INSURANCE = "read_insurance"
    APPROVE_ORDER = "approve_order"
