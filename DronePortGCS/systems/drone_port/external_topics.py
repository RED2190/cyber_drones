"""Внешние топики DronePort (SITL и др.)."""

from __future__ import annotations

import os

from sdk.topic_naming import clean_topic_part


def _env(name: str, default: str) -> str:
    return clean_topic_part(os.getenv(name, default)) or default


class ExternalTopics:
    """Топик HOME для SITL verifier (схема sitl-drone-home.json)."""

    SITL_HOME = _env("SITL_HOME_TOPIC", "sitl-drone-home")


__all__ = ["ExternalTopics"]
