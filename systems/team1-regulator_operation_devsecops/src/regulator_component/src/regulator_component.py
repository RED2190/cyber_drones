"""RegulatorComponent — in-memory SO and certificates.

NOTE: Этот файл предназначен для среды интегратора, где доступны пакеты
broker и sdk. Для локального запуска используйте __main__.py.
"""
from __future__ import annotations

from typing import Any, Dict

# broker и sdk — внешние зависимости из репозитория интегратора
from broker.system_bus import SystemBus
from sdk.base_component import BaseComponent

from ..topics import (
    ComponentTopics,
    RegulatorActions,
    SECURITY_OBJECTIVES,
)


class RegulatorComponent(BaseComponent):
    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str = ComponentTopics.REGULATOR_COMPONENT,
    ):
        self._systems: Dict[str, Dict[str, Any]] = {}
        self._drone_certs: Dict[str, str] = {}
        self._operator_certs: Dict[str, str] = {}
        super().__init__(
            component_id=component_id,
            component_type="regulator",
            topic=topic,
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler(RegulatorActions.REGISTER_SYSTEM, self._handle_register_system)
        self.register_handler(RegulatorActions.VERIFY_SYSTEM, self._handle_verify_system)
        self.register_handler(RegulatorActions.REGISTER_DRONE_CERT, self._handle_register_drone_cert)
        self.register_handler(RegulatorActions.VERIFY_DRONE_CERT, self._handle_verify_drone_cert)
        self.register_handler(RegulatorActions.REGISTER_OPERATOR_CERT, self._handle_register_operator_cert)
        self.register_handler(RegulatorActions.VERIFY_OPERATOR_CERT, self._handle_verify_operator_cert)

    def _handle_register_system(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {}) or {}
        system_id = str(payload.get("system_id", "")).strip()
        system_type = str(payload.get("system_type", "unknown")).strip()
        if not system_id:
            raise ValueError("system_id is required")
        self._systems[system_id] = {"system_type": system_type, "security_objectives": list(SECURITY_OBJECTIVES)}
        return {"registered": True, "system_id": system_id, "security_objectives": list(SECURITY_OBJECTIVES)}

    def _handle_verify_system(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {}) or {}
        system_id = str(payload.get("system_id", "")).strip()
        ok = system_id in self._systems
        return {"verified": ok, "system_id": system_id}

    def _handle_register_drone_cert(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {}) or {}
        drone_id = str(payload.get("drone_id", "")).strip()
        if not drone_id:
            raise ValueError("drone_id is required")
        cert_id = f"cert-drone-{drone_id}"
        self._drone_certs[cert_id] = drone_id
        return {"certificate_id": cert_id, "drone_id": drone_id}

    def _handle_verify_drone_cert(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {}) or {}
        drone_id = str(payload.get("drone_id", "")).strip()
        certificate_id = str(payload.get("certificate_id", "")).strip()
        if not drone_id or not certificate_id:
            raise ValueError("drone_id and certificate_id are required")
        valid = self._drone_certs.get(certificate_id) == drone_id
        return {"valid": valid, "drone_id": drone_id, "certificate_id": certificate_id}

    def _handle_register_operator_cert(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {}) or {}
        operator_id = str(payload.get("operator_id", "")).strip()
        if not operator_id:
            raise ValueError("operator_id is required")
        cert_id = f"cert-op-{operator_id}"
        self._operator_certs[cert_id] = operator_id
        return {"certificate_id": cert_id, "operator_id": operator_id}

    def _handle_verify_operator_cert(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {}) or {}
        operator_id = str(payload.get("operator_id", "")).strip()
        certificate_id = str(payload.get("certificate_id", "")).strip()
        if not operator_id or not certificate_id:
            raise ValueError("operator_id and certificate_id are required")
        valid = self._operator_certs.get(certificate_id) == operator_id
        return {"valid": valid, "operator_id": operator_id, "certificate_id": certificate_id}
