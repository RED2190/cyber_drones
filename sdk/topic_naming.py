"""
Построение имён топиков для систем с префиксом SYSTEM_NAMESPACE
и сегментом системы (SYSTEM_NAME / GCS_SYSTEM_NAME).

Итоговый формат:
    {namespace}components.{system_slug}.{component_suffix}

Примеры (без namespace):
    components.drone_port.charging_manager
    components.gcs.drone_store

С namespace=fleet_1:
    fleet_1.components.drone_port.charging_manager
"""
import re
import os


def clean_topic_part(value: str) -> str:
    """Sanitize a topic segment: lowercase, replace spaces/invalid chars with '_'.

    Used by GCS external_topics.py to normalise env-var values before embedding
    them into topic strings.

    Examples::

        clean_topic_part("My System") -> "my_system"
        clean_topic_part("Agrodron")  -> "agrodron"   # preserves case intentionally
        clean_topic_part("")          -> ""
    """
    if not value:
        return value
    # Replace whitespace and characters that are invalid in topic names with '_'
    cleaned = re.sub(r"[\s/\\]+", "_", value.strip())
    # Remove any leading/trailing underscores produced by the replacement
    return cleaned.strip("_")


def build_component_topic(
    component_suffix: str,
    *,
    system_env_var: str = "SYSTEM_NAME",
    default_system_name: str = "drone_port",
) -> str:
    """
    Возвращает полное имя топика компонента.

    Args:
        component_suffix: короткое имя (например ``charging_manager``, ``registry``).
        system_env_var: переменная окружения со slug системы.
        default_system_name: значение по умолчанию, если переменная не задана.
    """
    ns = os.environ.get("SYSTEM_NAMESPACE", "")
    prefix = f"{ns}." if ns else ""
    system = os.environ.get(system_env_var, default_system_name)
    return f"{prefix}components.{system}.{component_suffix}"
