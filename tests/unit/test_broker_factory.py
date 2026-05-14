"""Тесты broker/bus_factory — фабрика create_system_bus."""
import pytest
from unittest.mock import patch, MagicMock

from broker.src.system_bus import SystemBus


def test_kafka_type_returns_kafka_bus():
    with patch("broker.src.bus_factory.KafkaSystemBus") as mock_cls:
        mock_cls.return_value = MagicMock(spec=SystemBus)
        from broker.bus_factory import create_system_bus
        bus = create_system_bus(bus_type="kafka", client_id="test")
        mock_cls.assert_called_once()
        assert isinstance(bus, SystemBus)


def test_mqtt_type_returns_mqtt_bus():
    with patch("broker.src.bus_factory.MQTTSystemBus") as mock_cls:
        mock_cls.return_value = MagicMock(spec=SystemBus)
        from broker.bus_factory import create_system_bus
        bus = create_system_bus(bus_type="mqtt", client_id="test")
        mock_cls.assert_called_once()
        assert isinstance(bus, SystemBus)


def test_unknown_type_raises():
    from broker.bus_factory import create_system_bus
    with pytest.raises(ValueError, match="Unknown broker type"):
        create_system_bus(bus_type="redis")


def test_type_from_config_dict():
    with patch("broker.src.bus_factory.MQTTSystemBus") as mock_cls:
        mock_cls.return_value = MagicMock(spec=SystemBus)
        from broker.bus_factory import create_system_bus
        bus = create_system_bus(
            client_id="test",
            config={"broker": {"type": "mqtt"}}
        )
        mock_cls.assert_called_once()
        assert isinstance(bus, SystemBus)


def test_system_bus_cannot_instantiate_abc():
    with pytest.raises(TypeError):
        SystemBus()


def test_system_bus_has_required_methods():
    methods = ["publish", "subscribe", "unsubscribe", "request",
               "request_async", "start", "stop", "respond"]
    for m in methods:
        assert hasattr(SystemBus, m), f"SystemBus missing method: {m}"
