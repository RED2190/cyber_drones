"""Gateway topics/actions for Agrodron system facade."""

import os


class SystemTopics:
    AGRODRON = os.environ.get("AGRODRON_GATEWAY_TOPIC", "systems.agrodron")


class ComponentTopics:
    SECURITY_MONITOR = (
        os.environ.get("SECURITY_MONITOR_TOPIC")
        or "v1.Agrodron.Agrodron001.security_monitor"
    )
    MISSION_HANDLER = (
        os.environ.get("MISSION_HANDLER_TOPIC")
        or "v1.Agrodron.Agrodron001.mission_handler"
    )
    AUTOPILOT = (
        os.environ.get("AUTOPILOT_TOPIC")
        or "v1.Agrodron.Agrodron001.autopilot"
    )
    TELEMETRY = (
        os.environ.get("TELEMETRY_TOPIC")
        or "v1.Agrodron.Agrodron001.telemetry"
    )


class GatewayActions:
    LOAD_MISSION = "load_mission"
    VALIDATE_ONLY = "validate_only"
    CMD = "cmd"
    GET_STATE = "get_state"
