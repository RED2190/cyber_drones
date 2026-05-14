"""
InsurerGateway — координатор alt_insurer.

Принимает запросы на топик systems.alt_insurer и проксирует
к компоненту insurance_service.
"""
from typing import Optional

from sdk.base_gateway import BaseGateway
from broker.system_bus import SystemBus

from systems.alt_insurer.src.gateway.topics import (
    SystemTopics,
    ComponentTopics,
    GatewayActions,
)


class InsurerGateway(BaseGateway):

    ACTION_ROUTING = {
        GatewayActions.ANNUAL_INSURANCE:  ComponentTopics.INSURANCE_SERVICE,
        GatewayActions.MISSION_INSURANCE: ComponentTopics.INSURANCE_SERVICE,
        GatewayActions.CALCULATE_POLICY:  ComponentTopics.INSURANCE_SERVICE,
        GatewayActions.PURCHASE_POLICY:   ComponentTopics.INSURANCE_SERVICE,
        GatewayActions.REPORT_INCIDENT:   ComponentTopics.INSURANCE_SERVICE,
        GatewayActions.TERMINATE_POLICY:  ComponentTopics.INSURANCE_SERVICE,
    }

    PROXY_TIMEOUT = 15.0

    def __init__(
        self,
        system_id: str,
        bus: SystemBus,
        health_port: Optional[int] = None,
        topic_override: Optional[str] = None,
    ):
        super().__init__(
            system_id=system_id,
            system_type="alt_insurer",
            topic=topic_override or SystemTopics.DUMMY_INSURER,
            bus=bus,
            health_port=health_port,
        )
