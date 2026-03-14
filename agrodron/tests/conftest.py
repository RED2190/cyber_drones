"""
Общие фикстуры для интеграционных тестов AgroDron.

Используется при запуске: pytest agrodron/tests/ -c config/pyproject.toml
"""
import os

import pytest


@pytest.fixture(scope="session")
def broker_type():
    """Тип брокера из окружения (mqtt/kafka)."""
    return os.environ.get("BROKER_TYPE", "mqtt").strip().lower()


@pytest.fixture(scope="session")
def mqtt_broker_host():
    """Хост MQTT брокера для интеграционных тестов."""
    return os.environ.get("MQTT_BROKER", "localhost").strip()


@pytest.fixture(scope="session")
def system_name():
    """Имя системы (префикс топиков)."""
    return os.environ.get("SYSTEM_NAME", "agrodron").strip()


@pytest.fixture(scope="session")
def security_monitor_topic(system_name):
    """Топик монитора безопасности."""
    return f"{system_name}.security_monitor"


@pytest.fixture(scope="session")
def topic(system_name):
    """Фабрика топиков: topic('motors') -> agrodron.motors."""

    def _topic(component: str) -> str:
        return f"{system_name}.{component}"

    return _topic


def pytest_configure(config):
    """Регистрация маркеров."""
    config.addinivalue_line("markers", "full_system: полный прогон системы (ОРВД, SITL, МБ и т.д.)")
    config.addinivalue_line("markers", "integration: интеграционный тест с реальным брокером")


def pytest_runtest_setup(item):
    """Перед каждым тестом вывести краткое описание (первая строка docstring)."""
    if item.function.__doc__:
        doc = item.function.__doc__.strip().split("\n")[0].strip()
        if doc:
            print(f"\n  >> {doc}")
