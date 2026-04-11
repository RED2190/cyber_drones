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
from sdk.base_system import BaseSystem

__all__ = ["Message", "create_response", "BaseComponent", "BaseSystem"]
