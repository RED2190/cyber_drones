"""Reusable helpers for versioned, instance-safe topic naming."""

from __future__ import annotations

import os


def clean_topic_part(value: str) -> str:
    return (value or "").strip().replace("/", ".")


def topic_version(env_var: str = "TOPIC_VERSION", default: str = "v1") -> str:
    return clean_topic_part(os.getenv(env_var, default)) or default


def system_name(env_var: str, default: str) -> str:
    return clean_topic_part(os.getenv(env_var, default)) or default


def instance_id(env_var: str = "INSTANCE_ID", default: str = "1") -> str:
    return clean_topic_part(os.getenv(env_var, default)) or default


def build_component_topic(
    component: str,
    *,
    system_env_var: str,
    default_system_name: str,
    version_env_var: str = "TOPIC_VERSION",
    default_version: str = "v1",
    instance_env_var: str = "INSTANCE_ID",
    default_instance_id: str = "1",
) -> str:
    component_name = clean_topic_part(component)
    return ".".join(
        [
            topic_version(version_env_var, default_version),
            system_name(system_env_var, default_system_name),
            instance_id(instance_env_var, default_instance_id),
            component_name,
        ]
    )
