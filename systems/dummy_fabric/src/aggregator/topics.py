"""Топики и actions для Aggregator в составе dummy_fabric."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    AGGREGATOR = f"{_P}components.fabric_aggregator"


class AggregatorActions:
    CREATE_ORDER = "create_order"
    ASSIGN_ORDER = "assign_order"
    READ_ORDER = "read_order"
    REQUEST_FLIGHT_PERMISSION = "request_flight_permission"
    FINALIZE_ORDER = "finalize_order"
