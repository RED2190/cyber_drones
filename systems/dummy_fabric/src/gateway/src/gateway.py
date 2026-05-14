"""
FabricGateway — координатор dummy_fabric.

Принимает запросы на топик systems.dummy_fabric и маршрутизирует
к компонентам-организациям по таблице ACTION_ROUTING.
"""
from typing import Optional

from sdk.base_gateway import BaseGateway
from broker.system_bus import SystemBus

from systems.dummy_fabric.src.gateway.topics import (
    SystemTopics,
    ComponentTopics,
    GatewayActions,
)


class FabricGateway(BaseGateway):

    ACTION_ROUTING = {
        GatewayActions.ISSUE_TYPE_CERTIFICATE: ComponentTopics.CERT_CENTER,
        GatewayActions.CERTIFY_FIRMWARE: ComponentTopics.CERT_CENTER,
        GatewayActions.CREATE_DRONE_PASS: ComponentTopics.CERT_CENTER,
        GatewayActions.READ_DRONE_PASS: ComponentTopics.CERT_CENTER,
        GatewayActions.LIST_DRONE_PASSES: ComponentTopics.CERT_CENTER,
        GatewayActions.CREATE_INSURANCE: ComponentTopics.INSURER,
        GatewayActions.READ_INSURANCE: ComponentTopics.INSURER,
        GatewayActions.APPROVE_ORDER: ComponentTopics.INSURER,
        GatewayActions.CREATE_ORDER: ComponentTopics.AGGREGATOR,
        GatewayActions.ASSIGN_ORDER: ComponentTopics.AGGREGATOR,
        GatewayActions.READ_ORDER: ComponentTopics.AGGREGATOR,
        GatewayActions.REQUEST_FLIGHT_PERMISSION: ComponentTopics.AGGREGATOR,
        GatewayActions.FINALIZE_ORDER: ComponentTopics.AGGREGATOR,
        GatewayActions.CONFIRM_ORDER: ComponentTopics.OPERATOR,
        GatewayActions.START_ORDER: ComponentTopics.OPERATOR,
        GatewayActions.FINISH_ORDER: ComponentTopics.OPERATOR,
        GatewayActions.APPROVE_FLIGHT_PERMISSION: ComponentTopics.ORVD,
    }

    PROXY_TIMEOUT = 60.0

    def __init__(
        self,
        system_id: str,
        bus: SystemBus,
        health_port: Optional[int] = None,
    ):
        super().__init__(
            system_id=system_id,
            system_type="dummy_fabric",
            topic=SystemTopics.DUMMY_FABRIC,
            bus=bus,
            health_port=health_port,
        )
