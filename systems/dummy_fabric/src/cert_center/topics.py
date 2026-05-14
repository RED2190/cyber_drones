"""Топики и actions для CertCenter в составе dummy_fabric."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    CERT_CENTER = f"{_P}components.fabric_cert_center"


class CertCenterActions:
    ISSUE_TYPE_CERTIFICATE = "issue_type_certificate"
    CERTIFY_FIRMWARE = "certify_firmware"
    CREATE_DRONE_PASS = "create_drone_pass"
    READ_DRONE_PASS = "read_drone_pass"
    LIST_DRONE_PASSES = "list_drone_passes"
