"""Топики и actions для ОрВД в составе dummy_fabric."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    ORVD = f"{_P}components.fabric_orvd"


class OrvdActions:
    APPROVE_FLIGHT_PERMISSION = "approve_flight_permission"
