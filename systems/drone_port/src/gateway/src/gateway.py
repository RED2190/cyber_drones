"""Gateway для внешнего взаимодействия с DronePort."""

from typing import Optional

from broker.system_bus import SystemBus
from sdk.base_gateway import BaseGateway

from ..topics import ComponentTopics, GatewayActions, SystemTopics


class DronePortGateway(BaseGateway):
    ACTION_ROUTING = {
        GatewayActions.GET_AVAILABLE_DRONES: ComponentTopics.ORCHESTRATOR,
        GatewayActions.REQUEST_LANDING: ComponentTopics.DRONE_MANAGER,
        GatewayActions.REQUEST_TAKEOFF: ComponentTopics.DRONE_MANAGER,
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
            system_type="drone_port",
            topic=SystemTopics.DRONE_PORT,
            bus=bus,
            health_port=health_port,
        )
