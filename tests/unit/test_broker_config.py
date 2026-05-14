"""Тесты broker/config.py — чтение конфигурации из env."""
import pytest


def test_get_kafka_bootstrap_default(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    monkeypatch.delenv("KAFKA_HOST", raising=False)
    monkeypatch.delenv("KAFKA_PORT", raising=False)
    from broker.config import get_kafka_bootstrap
    assert get_kafka_bootstrap() == "localhost:9092"


def test_get_kafka_bootstrap_from_env(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker1:9093,broker2:9093")
    from broker.config import get_kafka_bootstrap
    assert get_kafka_bootstrap() == "broker1:9093,broker2:9093"


def test_get_kafka_bootstrap_host_port(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    monkeypatch.setenv("KAFKA_HOST", "myhost")
    monkeypatch.setenv("KAFKA_PORT", "19092")
    from broker.config import get_kafka_bootstrap
    assert get_kafka_bootstrap() == "myhost:19092"


def test_get_mqtt_broker_default(monkeypatch):
    monkeypatch.delenv("MQTT_HOST", raising=False)
    monkeypatch.delenv("MQTT_BROKER", raising=False)
    monkeypatch.delenv("MQTT_PORT", raising=False)
    from broker.config import get_mqtt_broker
    assert get_mqtt_broker() == ("localhost", 1883)


def test_get_mqtt_broker_from_env(monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "mqtt.local")
    monkeypatch.setenv("MQTT_PORT", "11883")
    from broker.config import get_mqtt_broker
    assert get_mqtt_broker() == ("mqtt.local", 11883)
