"""
Утилиты для построения имён топиков компонентов.

Обёртка над topic_naming.build_component_topic с удобными shortcut-функциями,
используемыми в agrodron и других системах.

Итоговый формат:
    {SYSTEM_NAMESPACE.}components.{SYSTEM_NAME}.{suffix}

Примеры (SYSTEM_NAME=Agrodron):
    components.Agrodron.navigation
    components.Agrodron.autopilot
"""
import os

from sdk.topic_naming import build_component_topic


def system_name() -> str:
    """Возвращает имя системы из SYSTEM_NAME (по умолчанию 'drone')."""
    return os.environ.get("SYSTEM_NAME", "drone")


def instance_id() -> str:
    """Возвращает INSTANCE_ID системы (используется как drone_id для ORVD)."""
    return os.environ.get("INSTANCE_ID", f"{system_name()}001")


def topic_prefix() -> str:
    """Возвращает префикс системы: components.{SYSTEM_NAME}."""
    ns = os.environ.get("SYSTEM_NAMESPACE", "")
    prefix = f"{ns}." if ns else ""
    return f"{prefix}components.{system_name()}"


def topic_for(component_suffix: str) -> str:
    """
    Возвращает полное имя топика для компонента.

    topic_for("navigation") -> "components.Agrodron.navigation"
    """
    return build_component_topic(
        component_suffix,
        system_env_var="SYSTEM_NAME",
        default_system_name=system_name(),
    )
