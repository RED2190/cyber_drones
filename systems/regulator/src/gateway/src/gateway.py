"""RegulatorGateway — entry on systems.regulator."""
from typing import Optional

from broker.system_bus import SystemBus
from sdk.base_gateway import BaseGateway

from systems.regulator.src.gateway.topics import SystemTopics, ComponentTopics, GatewayActions


class RegulatorGateway(BaseGateway):
    ACTION_ROUTING = {
        GatewayActions.REGISTER_SYSTEM: ComponentTopics.REGULATOR_COMPONENT,
        GatewayActions.VERIFY_SYSTEM: ComponentTopics.REGULATOR_COMPONENT,
        GatewayActions.REGISTER_DRONE_CERT: ComponentTopics.REGULATOR_COMPONENT,
        GatewayActions.VERIFY_DRONE_CERT: ComponentTopics.REGULATOR_COMPONENT,
        GatewayActions.REGISTER_OPERATOR_CERT: ComponentTopics.REGULATOR_COMPONENT,
        GatewayActions.VERIFY_OPERATOR_CERT: ComponentTopics.REGULATOR_COMPONENT,
    }

    PROXY_TIMEOUT = 15.0

    def __init__(
        self,
        system_id: str,
        bus: SystemBus,
        health_port: Optional[int] = None,
    ):
        super().__init__(
            system_id=system_id,
            system_type="regulator",
            topic=SystemTopics.REGULATOR,
            bus=bus,
            health_port=health_port,
        )
