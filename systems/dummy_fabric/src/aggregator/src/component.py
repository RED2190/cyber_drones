"""Aggregator — компонент агрегатора (AggregatorMSP)."""
from typing import Dict, Any

from systems.dummy_fabric.src._base import BaseFabricComponent
from systems.dummy_fabric.src.aggregator.topics import AggregatorActions


class AggregatorComponent(BaseFabricComponent):

    def _register_handlers(self):
        self.register_handler(AggregatorActions.CREATE_ORDER, self._handle_create_order)
        self.register_handler(AggregatorActions.ASSIGN_ORDER, self._handle_assign_order)
        self.register_handler(AggregatorActions.READ_ORDER, self._handle_read_order)
        self.register_handler(AggregatorActions.REQUEST_FLIGHT_PERMISSION, self._handle_request_fp)
        self.register_handler(AggregatorActions.FINALIZE_ORDER, self._handle_finalize_order)

    def _handle_create_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "OrderContract:CreateOrder",
            [p["id"], p["aggregator_id"], p.get("operator_id", ""),
             p.get("drone_id", ""), p["insurer_id"], p["cert_center_id"],
             p["developer_id"], str(p["fleet_price"]), str(p["aggregator_fee"]),
             str(p["insurance_premium"]), str(p["risk_reserve"]),
             str(p["insurance_coverage_amount"]),
             p.get("mission_insurance_id", ""), str(p.get("details", "[]"))],
        )

    def _handle_assign_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "OrderContract:AssignOrder",
            [p["order_id"], p["operator_id"], p["drone_id"],
             str(p.get("details", "[]"))],
        )

    def _handle_read_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric("OrderContract:ReadOrder", [p["id"]], action="query")

    def _handle_request_fp(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "OrderContract:RequestFlightPermission",
            [p["order_id"], p["valid_from"], p["valid_to"]],
        )

    def _handle_finalize_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric("OrderContract:FinalizeOrder", [p["order_id"]])
