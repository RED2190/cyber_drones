"""Gateway topics/actions for Agrodron system facade."""

import os

from systems.agrodron.src.topic_utils import topic_for


class SystemTopics:
    AGRODRON = os.environ.get("AGRODRON_GATEWAY_TOPIC", "systems.agrodron")


class ComponentTopics:
    SECURITY_MONITOR = os.environ.get("SECURITY_MONITOR_TOPIC") or topic_for("security_monitor")
    MISSION_HANDLER = os.environ.get("MISSION_HANDLER_TOPIC") or topic_for("mission_handler")
    AUTOPILOT = os.environ.get("AUTOPILOT_TOPIC") or topic_for("autopilot")
    TELEMETRY = os.environ.get("TELEMETRY_TOPIC") or topic_for("telemetry")


class GatewayActions:
    LOAD_MISSION = "load_mission"
    VALIDATE_ONLY = "validate_only"
    CMD = "cmd"
    GET_STATE = "get_state"
