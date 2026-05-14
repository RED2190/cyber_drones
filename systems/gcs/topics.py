"""Внешние топики и actions GCS для взаимодействия с AgroDron."""

import os

from .src.gateway.topics import GatewayActions, SystemTopics


class DroneTopics:
    SECURITY_MONITOR = os.getenv("AGRODRON_SECURITY_MONITOR_TOPIC", "").strip()
    MISSION_HANDLER = os.getenv("AGRODRON_MISSION_HANDLER_TOPIC", "").strip()
    AUTOPILOT = os.getenv("AGRODRON_AUTOPILOT_TOPIC", "").strip()
    TELEMETRY = os.getenv("AGRODRON_TELEMETRY_TOPIC", "").strip()

    @classmethod
    def all(cls) -> list[str]:
        return [
            cls.SECURITY_MONITOR,
            cls.MISSION_HANDLER,
            cls.AUTOPILOT,
            cls.TELEMETRY,
        ]


class DroneActions:
    PROXY_REQUEST = "proxy_request"
    LOAD_MISSION = "load_mission"
    CMD = "cmd"
    TELEMETRY_GET = "get_state"


__all__ = ["DroneTopics", "DroneActions", "SystemTopics", "GatewayActions"]
