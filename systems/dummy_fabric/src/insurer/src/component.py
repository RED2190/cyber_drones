"""Insurer — компонент страховщика (InsurerMSP)."""
from typing import Dict, Any

from systems.dummy_fabric.src._base import BaseFabricComponent
from systems.dummy_fabric.src.insurer.topics import InsurerActions


class InsurerComponent(BaseFabricComponent):

    def _register_handlers(self):
        self.register_handler(InsurerActions.CREATE_INSURANCE, self._handle_create_insurance)
        self.register_handler(InsurerActions.READ_INSURANCE, self._handle_read_insurance)
        self.register_handler(InsurerActions.APPROVE_ORDER, self._handle_approve_order)

    def _handle_create_insurance(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "DronePropertiesContract:CreateInsuranceRecord",
            [p["drone_id"], p["insurer_id"], str(p["coverage_amount"]),
             str(p.get("incident_count", 0)),
             p.get("valid_from", ""), p.get("valid_to", "")],
        )

    def _handle_read_insurance(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "DronePropertiesContract:ReadInsuranceRecord",
            [p["drone_id"]],
            action="query",
        )

    def _handle_approve_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric("OrderContract:ApproveOrder", [p["order_id"]])
