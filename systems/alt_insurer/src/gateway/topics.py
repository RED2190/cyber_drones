"""Топики и actions для Gateway alt_insurer."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    DUMMY_INSURER = f"{_P}systems.alt_insurer"


class ComponentTopics:
    INSURANCE_SERVICE = f"{_P}components.insurer_service"

    @classmethod
    def all(cls) -> list:
        return [cls.INSURANCE_SERVICE]


class GatewayActions:
    ANNUAL_INSURANCE = "annual_insurance"
    MISSION_INSURANCE = "mission_insurance"
    CALCULATE_POLICY = "calculate_policy"
    PURCHASE_POLICY = "purchase_policy"
    REPORT_INCIDENT = "report_incident"
    TERMINATE_POLICY = "terminate_policy"
