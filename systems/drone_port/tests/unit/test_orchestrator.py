from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions
from systems.drone_port.src.orchestrator.src.orchestrator import Orchestrator
from systems.drone_port.src.orchestrator.topics import OrchestratorActions

def test_registers_orchestrator_handlers(mock_bus):
    orchestrator = Orchestrator(component_id="orchestrator", name="Orchestrator", bus=mock_bus)
    assert OrchestratorActions.GET_AVAILABLE_DRONES in orchestrator._handlers

def test_get_available_drones_returns_drone_list(mock_bus):
    orchestrator = Orchestrator(component_id="orchestrator", name="Orchestrator", bus=mock_bus)
    mock_bus.request.return_value = {"success": True, "payload": {"drones": [{"drone_id": "DR-1"}]}}

    result = orchestrator._handle_get_available_drones({"payload": {}})

    assert result == {"drones": [{"drone_id": "DR-1"}], "from": "orchestrator"}
    mock_bus.request.assert_called_once_with(
        RegistryTopics.DRONE_REGISTRY,
        {"action": DroneRegistryActions.GET_AVAILABLE_DRONES, "payload": {}},
        timeout=5.0,
    )

def test_get_available_drones_returns_empty_list_when_payload_missing(mock_bus):
    orchestrator = Orchestrator(component_id="orchestrator", name="Orchestrator", bus=mock_bus)
    mock_bus.request.return_value = {"success": True}

    result = orchestrator._handle_get_available_drones({"payload": {}})

    assert result == {"drones": [], "from": "orchestrator"}

def test_get_available_drones_returns_empty_list_when_drones_not_list(mock_bus):
    orchestrator = Orchestrator(component_id="orchestrator", name="Orchestrator", bus=mock_bus)
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"drones": "not-a-list"},
    }

    result = orchestrator._handle_get_available_drones({"payload": {}})

    assert result == {"drones": [], "from": "orchestrator"}

def test_get_available_drones_returns_error_on_failed_request(mock_bus):
    orchestrator = Orchestrator(component_id="orchestrator", name="Orchestrator", bus=mock_bus)
    mock_bus.request.return_value = None

    result = orchestrator._handle_get_available_drones({"payload": {}})

    assert result == {
        "error": "Failed to get available drones",
        "from": "orchestrator",
    }

def test_get_available_drones_returns_error_when_success_false(mock_bus):
    orchestrator = Orchestrator(component_id="orchestrator", name="Orchestrator", bus=mock_bus)
    mock_bus.request.return_value = {
        "success": False,
        "payload": {"drones": [{"drone_id": "DR-1"}]},
    }

    result = orchestrator._handle_get_available_drones({"payload": {}})

    assert result == {
        "error": "Failed to get available drones",
        "from": "orchestrator",
    }

def test_get_available_drones_uses_component_id_in_response(mock_bus):
    orchestrator = Orchestrator(component_id="orch-42", name="Orchestrator", bus=mock_bus)
    mock_bus.request.return_value = {"success": True, "payload": {"drones": []}}

    result = orchestrator._handle_get_available_drones({"payload": {}})

    assert result["from"] == "orch-42"
