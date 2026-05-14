"""
OrvdGateway - координатор orvd_system.

Принимает:
- внутренние запросы на systems.orvd_system
- внешние запросы на v1.ORVD.ORVD001.main (Agrodron API)

Проксирует к OrvdComponent.
"""
from typing import Optional

from sdk.base_gateway import BaseGateway
from broker.system_bus import SystemBus

from systems.orvd_system.src.gateway.topics import (
    SystemTopics,
    ComponentTopics,
    GatewayActions,
)


class OrvdGateway(BaseGateway):

    ACTION_ROUTING = {
        GatewayActions.REGISTER_DRONE: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.REGISTER_MISSION: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.AUTHORIZE_MISSION: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.REQUEST_TAKEOFF: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.REVOKE_TAKEOFF: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.SEND_TELEMETRY: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.REQUEST_TELEMETRY: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.ADD_NO_FLY_ZONE: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.REMOVE_NO_FLY_ZONE: ComponentTopics.ORVD_COMPONENT,
        GatewayActions.GET_HISTORY: ComponentTopics.ORVD_COMPONENT,
        

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
            system_type="orvd_system",
            topic=SystemTopics.ORVD_SYSTEM,
            bus=bus,
            health_port=health_port,
        )

        bus.subscribe(SystemTopics.ORVD_EXTERNAL, self._handle_message)

        print(f"[ORVD] Gateway listening on:")
        print(f"  - {SystemTopics.ORVD_SYSTEM}")
        print(f"  - {SystemTopics.ORVD_EXTERNAL}")