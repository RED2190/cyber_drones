import sys
import types
from unittest.mock import MagicMock

import pytest
import redis

flask_stub = types.ModuleType("flask")
flask_stub.Flask = type("Flask", (), {})
flask_stub.jsonify = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
sys.modules.setdefault("flask", flask_stub)


@pytest.fixture
def mock_bus():
    return MagicMock()


@pytest.fixture
def patch_redis_backend(monkeypatch):
    fake_client = MagicMock()
    fake_client.ping.return_value = True

    def fake_redis(*args, **kwargs):
        return fake_client

    monkeypatch.setattr(redis, "Redis", fake_redis)
    return fake_client
