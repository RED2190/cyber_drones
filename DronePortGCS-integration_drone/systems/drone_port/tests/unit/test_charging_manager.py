from systems.drone_port.src.charging_manager.src import charging_manager as charging_manager_module
from systems.drone_port.src.charging_manager.src.charging_manager import ChargingManager
from systems.drone_port.src.charging_manager.topics import ComponentTopics
from systems.drone_port.src.drone_registry.topics import DroneRegistryActions


def test_start_charging_publishes_started_event_and_spawns_worker(mock_bus, monkeypatch):
    captured = {}

    class FakeThread:
        def __init__(self, target, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(charging_manager_module.threading, "Thread", FakeThread)
    manager = ChargingManager(component_id="charging_manager", name="Charging", bus=mock_bus)

    result = manager._handle_start_charging(
        {"payload": {"drone_id": "DR-1", "battery": 45.0}}
    )

    assert result is None
    mock_bus.publish.assert_called_once_with(
        ComponentTopics.DRONE_REGISTRY,
        {
            "action": DroneRegistryActions.CHARGING_STARTED,
            "payload": {"drone_id": "DR-1"},
            "sender": "charging_manager",
        },
    )
    assert captured == {
        "target": manager._simulate_charging,
        "args": ("DR-1", 45.0),
        "daemon": True,
        "started": True,
    }


def test_simulate_charging_publishes_updates_until_full(mock_bus, monkeypatch):
    manager = ChargingManager(component_id="charging_manager", name="Charging", bus=mock_bus)
    monkeypatch.setattr(charging_manager_module.time, "sleep", lambda *_args, **_kwargs: None)

    manager._simulate_charging("DR-2", 85.0)

    published = [call.args for call in mock_bus.publish.call_args_list]
    assert published == [
        (
            ComponentTopics.DRONE_REGISTRY,
            {
                "action": DroneRegistryActions.UPDATE_BATTERY,
                "payload": {"drone_id": "DR-2", "battery": 95.0},
                "sender": "charging_manager",
            },
        ),
        (
            ComponentTopics.DRONE_REGISTRY,
            {
                "action": DroneRegistryActions.UPDATE_BATTERY,
                "payload": {"drone_id": "DR-2", "battery": 100.0},
                "sender": "charging_manager",
            },
        ),
    ]
