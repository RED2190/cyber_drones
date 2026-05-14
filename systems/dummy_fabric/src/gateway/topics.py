"""Топики и actions для Gateway dummy_fabric."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    DUMMY_FABRIC = f"{_P}systems.dummy_fabric"


class ComponentTopics:
    AGGREGATOR = f"{_P}components.fabric_aggregator"
    CERT_CENTER = f"{_P}components.fabric_cert_center"
    INSURER = f"{_P}components.fabric_insurer"
    OPERATOR = f"{_P}components.fabric_operator"
    ORVD = f"{_P}components.fabric_orvd"

    @classmethod
    def all(cls) -> list:
        return [
            cls.AGGREGATOR, cls.CERT_CENTER, cls.INSURER,
            cls.OPERATOR, cls.ORVD,
        ]


class GatewayActions:
    ISSUE_TYPE_CERTIFICATE = "issue_type_certificate"
    CERTIFY_FIRMWARE = "certify_firmware"
    CREATE_DRONE_PASS = "create_drone_pass"
    READ_DRONE_PASS = "read_drone_pass"
    LIST_DRONE_PASSES = "list_drone_passes"
    CREATE_INSURANCE = "create_insurance"
    READ_INSURANCE = "read_insurance"
    APPROVE_ORDER = "approve_order"
    CREATE_ORDER = "create_order"
    ASSIGN_ORDER = "assign_order"
    READ_ORDER = "read_order"
    REQUEST_FLIGHT_PERMISSION = "request_flight_permission"
    FINALIZE_ORDER = "finalize_order"
    CONFIRM_ORDER = "confirm_order"
    START_ORDER = "start_order"
    FINISH_ORDER = "finish_order"
    APPROVE_FLIGHT_PERMISSION = "approve_flight_permission"
