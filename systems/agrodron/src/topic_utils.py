"""
Топики компонентов Agrodron: v1.<SYSTEM_NAME>.<INSTANCE_ID>.<suffix>
(совпадает с подстановкой ${SYSTEM_NAME} в политиках безопасности).
"""
from __future__ import annotations

from sdk.topic_utils import instance_id as _instance_id
from sdk.topic_utils import system_name as _system_name
from sdk.topic_utils import topic_prefix as _topic_prefix


def system_name() -> str:
    return _system_name()


def instance_id() -> str:
    return _instance_id()


def topic_prefix() -> str:
    return _topic_prefix()


def topic_for(component_suffix: str) -> str:
    return f"{_topic_prefix()}.{component_suffix}"
