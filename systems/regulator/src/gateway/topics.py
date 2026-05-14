"""Topics and actions for Regulator gateway."""
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""

SECURITY_OBJECTIVES = [f"SO_{i}" for i in range(1, 12)]


class SystemTopics:
    REGULATOR = f"{_P}systems.regulator"


class ComponentTopics:
    REGULATOR_COMPONENT = f"{_P}components.regulator"

    @classmethod
    def all(cls) -> list:
        return [cls.REGULATOR_COMPONENT]


class GatewayActions:
    REGISTER_SYSTEM = "register_system"
    VERIFY_SYSTEM = "verify_system"
    REGISTER_DRONE_CERT = "register_drone_cert"
    VERIFY_DRONE_CERT = "verify_drone_cert"
    REGISTER_OPERATOR_CERT = "register_operator_cert"
    VERIFY_OPERATOR_CERT = "verify_operator_cert"
