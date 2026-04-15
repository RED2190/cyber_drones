from __future__ import annotations

import os

from broker.src.system_bus import SystemBus
from sdk.base_component import BaseComponent

try:
    import redis
except ImportError:
    redis = None  # type: ignore


class BaseRedisStoreComponent(BaseComponent):
    def __init__(
        self,
        component_id: str,
        component_type: str,
        topic: str,
        bus: SystemBus,
        redis_db_env: str,
        redis_default_db: int,
    ):
        self.component_id = component_id
        self.redis_client = None
        self._redis_db_env = redis_db_env
        self._redis_default_db = redis_default_db
        self._init_backend()

        super().__init__(
            component_id=component_id,
            component_type=component_type,
            topic=topic,
            bus=bus,
        )

    def _init_backend(self) -> None:
        if redis is None:
            raise RuntimeError("redis package is not installed. Install dependency 'redis>=5.0.0'")

        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv(self._redis_db_env, str(self._redis_default_db)))
        password = os.getenv("REDIS_PASSWORD")

        try:
            client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self.redis_client = client
            print(f"[{self.component_id}] connected to Redis at {host}:{port}/{db}")
        except Exception as exc:
            raise RuntimeError(f"[{self.component_id}] Redis unavailable: {exc}") from exc
