"""
OperatorGateway — координатор Operator system.

Принимает запросы на топик systems.operator и проксирует
к внутренним компонентам по таблице ACTION_ROUTING.
"""
from typing import Optional

from broker.system_bus import SystemBus
from sdk.base_gateway import BaseGateway

from systems.operator.src.gateway.topics import SystemTopics, ComponentTopics, GatewayActions


class OperatorGateway(BaseGateway):
    ACTION_ROUTING = {
        GatewayActions.REGISTER_DRONE: ComponentTopics.OPERATOR_COMPONENT,
        GatewayActions.REQUEST_AVAILABLE_DRONES: ComponentTopics.OPERATOR_COMPONENT,
        GatewayActions.SELECT_DRONE_AND_SEND_TO_AGGREGATOR: ComponentTopics.OPERATOR_COMPONENT,
        GatewayActions.BUY_INSURANCE_POLICY: ComponentTopics.OPERATOR_COMPONENT,
        GatewayActions.REGISTER_DRONE_IN_ORVD: ComponentTopics.OPERATOR_COMPONENT,
        GatewayActions.SEND_ORDER_TO_NUS: ComponentTopics.OPERATOR_COMPONENT,
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
            system_type="operator",
            topic=SystemTopics.OPERATOR,
            bus=bus,
            health_port=health_port,
        )

