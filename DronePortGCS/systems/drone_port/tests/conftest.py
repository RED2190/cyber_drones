from __future__ import annotations

from fnmatch import fnmatch
from types import SimpleNamespace
from unittest.mock import MagicMock
import sys
import types

import pytest

flask_stub = types.ModuleType("flask")
flask_stub.Flask = type("Flask", (), {})
flask_stub.jsonify = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
sys.modules.setdefault("flask", flask_stub)

redis_stub = types.ModuleType("redis")
redis_stub.Redis = type("Redis", (), {})
sys.modules.setdefault("redis", redis_stub)

from systems.drone_port.src.charging_manager.src import charging_manager as charging_manager_module
from systems.drone_port.src.drone_manager.src import drone_manager as drone_manager_module
from systems.drone_port.src.drone_registry.src import drone_registry as drone_registry_module
from systems.drone_port.src.state_store.src import state_store as state_store_module


class FakeRedis:
    def __init__(self):
        self.data = {}

    def exists(self, key):
        return key in self.data

    def hset(self, key, mapping):
        entry = self.data.setdefault(key, {})
        entry.update(mapping)
        return 1

    def hgetall(self, key):
        return dict(self.data.get(key, {}))

    def keys(self, pattern):
        return [key for key in self.data if fnmatch(key, pattern)]

    def delete(self, key):
        self.data.pop(key, None)
        return 1


class InMemoryBus:
    def __init__(self):
        self.components = {}
        self.requests = []
        self.publishes = []

    def register(self, component):
        self.components[component.topic] = component

    def request(self, topic, message, timeout=None):
        self.requests.append((topic, message, timeout))
        component = self.components.get(topic)
        if component is None:
            return None
        handler = component._handlers.get(message.get("action"))
        if handler is None:
            return None
        return handler(message)

    def publish(self, topic, message):
        self.publishes.append((topic, message))
        component = self.components.get(topic)
        if component is None:
            return True
        handler = component._handlers.get(message.get("action"))
        if handler is not None:
            handler(message)
        return True

    def respond(self, *_args, **_kwargs):
        return True

    def start(self):
        return None

    def stop(self):
        return None

    def subscribe(self, *_args, **_kwargs):
        return None

    def unsubscribe(self, *_args, **_kwargs):
        return None


@pytest.fixture
def mock_bus():
    bus = MagicMock()
    bus.request.return_value = None
    bus.publish.return_value = True
    bus.respond.return_value = True
    return bus


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def patch_droneport_redis(monkeypatch, fake_redis):
    monkeypatch.setattr(state_store_module.redis, "Redis", lambda **_kwargs: fake_redis)
    monkeypatch.setattr(drone_registry_module.redis, "Redis", lambda **_kwargs: fake_redis)
    return fake_redis


@pytest.fixture
def patch_drone_manager_external(monkeypatch):
    monkeypatch.setattr(
        drone_manager_module,
        "ExternalTopics",
        SimpleNamespace(SITL_HOME="sitl"),
        raising=False,
    )


@pytest.fixture
def immediate_thread(monkeypatch):
    class ImmediateThread:
        def __init__(self, target, args=(), daemon=None):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(charging_manager_module.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(charging_manager_module.time, "sleep", lambda *_args, **_kwargs: None)


@pytest.fixture
def integration_bus():
    return InMemoryBus()
