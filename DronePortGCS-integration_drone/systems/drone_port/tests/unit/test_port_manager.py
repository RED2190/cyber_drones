from systems.drone_port.src.port_manager.src.port_manager import PortManager
from systems.drone_port.src.port_manager.topics import ComponentTopics, PortManagerActions
from systems.drone_port.src.state_store.topics import StateStoreActions


def test_request_landing_reserves_first_free_port(mock_bus):
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = {
        "ports": [
            {"port_id": "P-01", "drone_id": "", "status": "free"},
            {"port_id": "P-02", "drone_id": "DR-9", "status": "reserved"},
        ]
    }

    result = manager._handle_request_landing({"payload": {"drone_id": "DR-1"}})

    assert result == {"port_id": "P-01"}
    mock_bus.publish.assert_called_once_with(
        ComponentTopics.STATE_STORE,
        {
            "action": StateStoreActions.UPDATE_PORT,
            "payload": {
                "port_id": "P-01",
                "drone_id": "DR-1",
                "status": "reserved",
            },
        },
    )


def test_get_port_status_proxies_state_store_response(mock_bus):
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = {"ports": [{"port_id": "P-03", "status": "free"}]}

    result = manager._handle_get_port_status({"payload": {}})

    assert result == {"ports": [{"port_id": "P-03", "status": "free"}]}
    mock_bus.request.assert_called_once_with(
        ComponentTopics.STATE_STORE,
        {"action": StateStoreActions.GET_ALL_PORTS, "payload": {}},
        timeout=3.0,
    )
