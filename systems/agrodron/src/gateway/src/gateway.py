"""System gateway for Agrodron external access."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from systems.agrodron.src.broker.system_bus import SystemBus
from systems.agrodron.src.sdk.base_system import BaseSystem

from src.gateway.topics import ComponentTopics, GatewayActions, SystemTopics


class AgrodronGateway(BaseSystem):
    PROXY_TIMEOUT_S = 10.0

    def __init__(self, system_id: str, bus: SystemBus, health_port: Optional[int] = None):
        self._external_sender = os.environ.get("AGRODRON_GATEWAY_SENDER") or os.environ.get("NUS_TOPIC") or "gateway"
        super().__init__(
            system_id=system_id,
            system_type="agrodron",
            topic=SystemTopics.AGRODRON,
            bus=bus,
            health_port=health_port,
        )

    def _register_handlers(self):
        self.register_handler(GatewayActions.LOAD_MISSION, self._handle_load_mission)
        self.register_handler(GatewayActions.VALIDATE_ONLY, self._handle_validate_only)
        self.register_handler(GatewayActions.CMD, self._handle_cmd)
        self.register_handler(GatewayActions.GET_STATE, self._handle_get_state)

    def _proxy_request(self, target_topic: str, target_action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        message = {
            "action": "proxy_request",
            "sender": self._external_sender,
            "payload": {
                "target": {
                    "topic": target_topic,
                    "action": target_action,
                },
                "data": data,
            },
        }
        response = self.bus.request(
            ComponentTopics.SECURITY_MONITOR,
            message,
            timeout=self.PROXY_TIMEOUT_S,
        )
        if not isinstance(response, dict):
            return {"ok": False, "error": "security_monitor_unavailable"}
        return response

    @staticmethod
    def _unwrap_target_response(response: Dict[str, Any]) -> Dict[str, Any]:
        target_response = response.get("target_response")
        if isinstance(target_response, dict):
            return target_response
        payload = response.get("payload")
        if isinstance(payload, dict):
            nested = payload.get("target_response")
            if isinstance(nested, dict):
                return nested
        return response

    @staticmethod
    def _extract_mission_payload(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        mission_id = payload.get("mission_id")
        wpl_content = payload.get("wpl_content")
        return mission_id, wpl_content

    def _handle_load_mission(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload") or {}
        mission_id, wpl_content = self._extract_mission_payload(payload)
        response = self._proxy_request(
            ComponentTopics.MISSION_HANDLER,
            GatewayActions.LOAD_MISSION,
            {
                "mission_id": mission_id,
                "wpl_content": wpl_content,
            },
        )
        return self._unwrap_target_response(response)

    def _handle_validate_only(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload") or {}
        response = self._proxy_request(
            ComponentTopics.MISSION_HANDLER,
            GatewayActions.VALIDATE_ONLY,
            {
                "mission_id": payload.get("mission_id"),
                "wpl_content": payload.get("wpl_content"),
            },
        )
        return self._unwrap_target_response(response)

    def _handle_cmd(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload") or {}
        response = self._proxy_request(
            ComponentTopics.AUTOPILOT,
            GatewayActions.CMD,
            {
                "command": payload.get("command"),
            },
        )
        return self._unwrap_target_response(response)

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        _ = message
        response = self._proxy_request(
            ComponentTopics.TELEMETRY,
            GatewayActions.GET_STATE,
            {},
        )
        return self._unwrap_target_response(response)
