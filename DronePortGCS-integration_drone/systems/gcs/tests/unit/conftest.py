import sys
import types
from unittest.mock import MagicMock

import pytest

flask_stub = types.ModuleType("flask")
flask_stub.Flask = type("Flask", (), {})
flask_stub.jsonify = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
sys.modules.setdefault("flask", flask_stub)

from sdk.base_redis_store_component import BaseRedisStoreComponent


@pytest.fixture
def mock_bus():
    return MagicMock()


@pytest.fixture
def patch_redis_backend(monkeypatch):
    def fake_init_backend(self):
        self.redis_client = MagicMock()

    monkeypatch.setattr(BaseRedisStoreComponent, "_init_backend", fake_init_backend)
