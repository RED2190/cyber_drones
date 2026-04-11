"""Внешние топики и actions GCS для взаимодействия с AgroDron."""

from systems.gcs.external_topics import ExternalTopics


class DroneTopics:
    SECURITY_MONITOR = ExternalTopics.AGRODRON_SECURITY_MONITOR
    MISSION_HANDLER = ExternalTopics.AGRODRON_MISSION_HANDLER
    AUTOPILOT = ExternalTopics.AGRODRON_AUTOPILOT
    TELEMETRY = ExternalTopics.AGRODRON_TELEMETRY

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


__all__ = ["DroneTopics", "DroneActions"]
