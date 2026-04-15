"""
SDK пакет для разработки компонентов и систем дрона.

Содержит:
- Протокол сообщений (Message, create_response)
- Базовые классы (BaseComponent, BaseSystem)

Для создания нового компонента/системы в отдельном репо:
    pip install -e path/to/common-repo
    from sdk import BaseComponent, BaseSystem, create_response
"""
from sdk.messages import Message, create_response
from sdk.base_component import BaseComponent
from sdk.base_redis_store_component import BaseRedisStoreComponent
from sdk.topic_naming import build_component_topic

try:
    from sdk.base_system import BaseSystem
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    BaseSystem = None

__all__ = ["Message", "create_response", "BaseComponent", "BaseSystem", "BaseRedisStoreComponent", "build_component_topic"]
