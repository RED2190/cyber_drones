"""CertCenter — компонент центра сертификации (CertCenterMSP)."""
from typing import Dict, Any

from systems.dummy_fabric.src._base import BaseFabricComponent
from systems.dummy_fabric.src.cert_center.topics import CertCenterActions


class CertCenterComponent(BaseFabricComponent):

    def _register_handlers(self):
        self.register_handler(CertCenterActions.ISSUE_TYPE_CERTIFICATE, self._handle_issue_type_cert)
        self.register_handler(CertCenterActions.CERTIFY_FIRMWARE, self._handle_certify_firmware)
        self.register_handler(CertCenterActions.CREATE_DRONE_PASS, self._handle_create_drone_pass)
        self.register_handler(CertCenterActions.READ_DRONE_PASS, self._handle_read_drone_pass)
        self.register_handler(CertCenterActions.LIST_DRONE_PASSES, self._handle_list_drone_passes)

    def _handle_issue_type_cert(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "DronePropertiesContract:IssueTypeCertificate",
            [p["id"], p["model"], p["manufacturer_id"], str(p.get("hardware_objectives", "[]"))],
        )

    def _handle_certify_firmware(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "FirmwareContract:CertifyFirmware",
            [p["id"], str(p.get("security_objectives", "[]")),
             str(p.get("software_objectives", "[]")),
             p.get("certified_at", ""), p.get("certified_by", "")],
        )

    def _handle_create_drone_pass(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "DronePropertiesContract:CreateDronePass",
            [p["id"], p["developer_id"], p["model"], p["drone_type"],
             str(p["weight_kg"]), str(p["max_flight_range_km"]),
             str(p["max_payload_weight_kg"]), str(p["release_year"]),
             p["firmware_id"], p["type_certificate_id"]],
        )

    def _handle_read_drone_pass(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        return self._call_fabric(
            "DronePropertiesContract:ReadDronePass",
            [p["id"]],
            action="query",
        )

    def _handle_list_drone_passes(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return self._call_fabric(
            "DronePropertiesContract:ListDronePasses",
            [],
            action="query",
        )
