"""
DummyGateway — координатор dummy_system.

Принимает запросы на топик systems.dummy_system и проксирует
к внутренним компонентам по таблице ACTION_ROUTING.
Отправитель знает только систему и action, не компоненты.
"""
from typing import Optional

from sdk.base_gateway import BaseGateway
from broker.system_bus import SystemBus

from systems.dummy_system.src.gateway.topics import (
    SystemTopics,
    ComponentTopics,
    GatewayActions,
)


class DummyGateway(BaseGateway):

    ACTION_ROUTING = {
        GatewayActions.ECHO: ComponentTopics.DUMMY_COMPONENT_A,
        GatewayActions.INCREMENT: ComponentTopics.DUMMY_COMPONENT_A,
        GatewayActions.GET_STATE: ComponentTopics.DUMMY_COMPONENT_A,
        GatewayActions.GET_DATA: ComponentTopics.DUMMY_COMPONENT_B,
    }

    PROXY_TIMEOUT = 10.0

    def __init__(
        self,
        system_id: str,
        bus: SystemBus,
        health_port: Optional[int] = None,
    ):
        super().__init__(
            system_id=system_id,
            system_type="dummy_system",
            topic=SystemTopics.DUMMY_SYSTEM,
            bus=bus,
            health_port=health_port,
        )
