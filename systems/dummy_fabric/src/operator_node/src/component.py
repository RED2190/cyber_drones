"""Operator — компонент эксплуатанта (OperatorMSP)."""
from typing import Dict, Any

from systems.dummy_fabric.src._base import BaseFabricComponent
from systems.dummy_fabric.src.operator_node.topics import OperatorActions


class OperatorComponent(BaseFabricComponent):

    def _register_handlers(self):
        self.register_handler(OperatorActions.CONFIRM_ORDER, self._handle_confirm_order)
        self.register_handler(OperatorActions.START_ORDER, self._handle_start_order)
        self.register_handler(OperatorActions.FINISH_ORDER, self._handle_finish_order)

    def _handle_confirm_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric("OrderContract:ConfirmOrder", [p["order_id"]])

    def _handle_start_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric("OrderContract:StartOrder", [p["order_id"]])

    def _handle_finish_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric("OrderContract:FinishOrder", [p["order_id"]])
