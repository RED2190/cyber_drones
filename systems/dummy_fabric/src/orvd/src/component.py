"""Orvd — компонент ОрВД (OrvdMSP)."""
from typing import Dict, Any

from systems.dummy_fabric.src._base import BaseFabricComponent
from systems.dummy_fabric.src.orvd.topics import OrvdActions


class OrvdComponent(BaseFabricComponent):

    def _register_handlers(self):
        self.register_handler(OrvdActions.APPROVE_FLIGHT_PERMISSION, self._handle_approve_fp)

    def _handle_approve_fp(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "OrderContract:ApproveFlightPermission",
            [p["permission_id"]],
        )
