"""
Юнит-тесты для Config.
Проверяем что переменные окружения корректно подхватываются.
"""
import pytest
import os
import importlib


class TestConfig:
    def test_default_broker_type_is_kafka(self):
        from src.regulator_component.src.config import Config
        os.environ.pop("BROKER_TYPE", None)
        # Перезагружаем модуль чтобы применились дефолты
        import src.regulator_component.src.config as cfg
        importlib.reload(cfg)
        assert cfg.Config.BROKER_TYPE == "kafka"

    def test_broker_type_from_env(self, monkeypatch):
        monkeypatch.setenv("BROKER_TYPE", "mqtt")
        import src.regulator_component.src.config as cfg
        importlib.reload(cfg)
        assert cfg.Config.BROKER_TYPE == "mqtt"

    def test_kafka_bootstrap_servers_from_env(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-host:9092")
        import src.regulator_component.src.config as cfg
        importlib.reload(cfg)
        assert cfg.Config.KAFKA_BOOTSTRAP_SERVERS == "kafka-host:9092"

    def test_mqtt_port_from_env(self, monkeypatch):
        monkeypatch.setenv("MQTT_PORT", "8883")
        import src.regulator_component.src.config as cfg
        importlib.reload(cfg)
        assert cfg.Config.MQTT_PORT == 8883

    def test_all_topic_constants_are_strings(self):
        from src.regulator_component.src.config import Config
        topics = [
            Config.TOPIC_FIRMWARE_REQUEST,
            Config.TOPIC_DRONE_REQUEST,
            Config.TOPIC_OPERATOR_REQUEST,
            Config.TOPIC_INSURER_REQUEST,
            Config.TOPIC_CERT_VERIFY_REQUEST,
            Config.TOPIC_CERT_REVOKE_REQUEST,
            Config.TOPIC_FIRMWARE_RESULT,
            Config.TOPIC_DRONE_RESULT,
            Config.TOPIC_OPERATOR_RESULT,
            Config.TOPIC_INSURER_RESPONSE,
            Config.TOPIC_CERT_VERIFY_RESPONSE,
            Config.TOPIC_CERT_REVOKE_RESPONSE,
        ]
        for topic in topics:
            assert isinstance(topic, str)
            assert len(topic) > 0

    def test_mock_flags_are_bool(self):
        from src.regulator_component.src.config import Config
        assert isinstance(Config.MOCK_SECURITY_TESTS, bool)
        assert isinstance(Config.MOCK_COVERAGE, bool)
