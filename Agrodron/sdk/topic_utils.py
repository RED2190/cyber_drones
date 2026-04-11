"""
Утилиты формирования топиков.

Формат: v1.{SystemName}.{InstanceID}.{component}
Пример: v1.Agrodron.Agrodron001.autopilot

Параметры задаются через переменные окружения:
  TOPIC_VERSION  — версия протокола (по умолчанию "v1")
  SYSTEM_NAME    — имя системы (по умолчанию "Agrodron")
  INSTANCE_ID    — идентификатор экземпляра (по умолчанию "Agrodron001")
"""
import os


def topic_version() -> str:
    return (os.environ.get("TOPIC_VERSION") or "v1").strip()


def system_name() -> str:
    return (os.environ.get("SYSTEM_NAME") or "Agrodron").strip()


def instance_id() -> str:
    return (os.environ.get("INSTANCE_ID") or "Agrodron001").strip()


def topic_prefix() -> str:
    return f"{topic_version()}.{system_name()}.{instance_id()}"


def topic_for(component: str) -> str:
    """Топик внутреннего компонента: v1.Agrodron.Agrodron001.{component}"""
    return f"{topic_prefix()}.{component}"
