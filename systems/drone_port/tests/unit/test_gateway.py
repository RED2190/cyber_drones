from systems.drone_port.src.gateway.src.gateway import DronePortGateway
from systems.drone_port.src.gateway.topics import ComponentTopics, GatewayActions, SystemTopics


def test_gateway_registers_all_routes(mock_bus):
    gateway = DronePortGateway(system_id="drone_port", bus=mock_bus)

    assert GatewayActions.GET_AVAILABLE_DRONES in gateway._handlers
    assert GatewayActions.REQUEST_LANDING in gateway._handlers
    assert GatewayActions.REQUEST_TAKEOFF in gateway._handlers
    assert gateway.topic == SystemTopics.DRONE_PORT


def test_gateway_proxies_to_orchestrator(mock_bus):
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"drones": [{"drone_id": "DR-1"}]},
    }
    gateway = DronePortGateway(system_id="drone_port", bus=mock_bus)

    result = gateway._handle_proxy(
        {
            "action": GatewayActions.GET_AVAILABLE_DRONES,
            "payload": {},
        }
    )

    assert result == {"drones": [{"drone_id": "DR-1"}]}
    mock_bus.request.assert_called_once_with(
        ComponentTopics.ORCHESTRATOR,
        {
            "action": GatewayActions.GET_AVAILABLE_DRONES,
            "sender": "drone_port",
            "payload": {},
        },
        timeout=10.0,
    )


def test_gateway_proxies_landing_to_drone_manager(mock_bus):
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"approved": True, "port_id": "P-01"},
    }
    gateway = DronePortGateway(system_id="drone_port", bus=mock_bus)

    result = gateway._handle_proxy(
        {
            "action": GatewayActions.REQUEST_LANDING,
            "payload": {"drone_id": "DR-1"},
        }
    )

    assert result == {"approved": True, "port_id": "P-01"}
    mock_bus.request.assert_called_once_with(
        ComponentTopics.DRONE_MANAGER,
        {
            "action": GatewayActions.REQUEST_LANDING,
            "sender": "drone_port",
            "payload": {"drone_id": "DR-1"},
        },
        timeout=10.0,
    )
