"""Внешние топики для интеграции GCS с AgroDron и смежными системами."""

from __future__ import annotations

import os

from sdk.topic_naming import clean_topic_part


def _env(name: str, default: str) -> str:
    return clean_topic_part(os.getenv(name, default)) or default


def _agrodron_prefix() -> str:
    version = _env("AGRODRON_TOPIC_VERSION", "v1")
    system_name = _env("AGRODRON_SYSTEM_NAME", "Agrodron")
    instance_id = _env("AGRODRON_INSTANCE_ID", "Agrodron001")
    return f"{version}.{system_name}.{instance_id}"


class ExternalTopics:
    AGRODRON_SECURITY_MONITOR = _env(
        "AGRODRON_SECURITY_MONITOR_TOPIC",
        f"{_agrodron_prefix()}.security_monitor",
    )
    AGRODRON_MISSION_HANDLER = _env(
        "AGRODRON_MISSION_HANDLER_TOPIC",
        f"{_agrodron_prefix()}.mission_handler",
    )
    AGRODRON_AUTOPILOT = _env(
        "AGRODRON_AUTOPILOT_TOPIC",
        f"{_agrodron_prefix()}.autopilot",
    )
    AGRODRON_TELEMETRY = _env(
        "AGRODRON_TELEMETRY_TOPIC",
        f"{_agrodron_prefix()}.telemetry",
    )

    @classmethod
    def agrodron_all(cls) -> list[str]:
        return [
            cls.AGRODRON_SECURITY_MONITOR,
            cls.AGRODRON_MISSION_HANDLER,
            cls.AGRODRON_AUTOPILOT,
            cls.AGRODRON_TELEMETRY,
        ]


__all__ = ["ExternalTopics"]
