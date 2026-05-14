"""Системные и внешние топики DronePort."""

import os

from .src.gateway.topics import GatewayActions, SystemTopics


class ExternalTopics:
    SITL_HOME = (os.environ.get("SITL_HOME_TOPIC") or "").strip()


__all__ = ["ExternalTopics", "SystemTopics", "GatewayActions"]
