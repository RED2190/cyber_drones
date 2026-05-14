import pytest

from systems.drone_port.src.port_manager.src.port_manager import PortManager
from systems.drone_port.src.port_manager.topics import ComponentTopics, PortManagerActions
from systems.drone_port.src.state_store.topics import StateStoreActions


@pytest.fixture
def component(mock_bus):
    return PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)


# -------------------------
# Регистрация обработчиков
# -------------------------
def test_registers_port_manager_handlers(component):
    """Все действия PortManager зарегистрированы в _handlers."""
    assert PortManagerActions.REQUEST_LANDING in component._handlers
    assert PortManagerActions.FREE_SLOT in component._handlers
    assert PortManagerActions.GET_PORT_STATUS in component._handlers


# -------------------------
# REQUEST_LANDING (_handle_request_landing)
# -------------------------
def test_request_landing_reserves_first_free_port(mock_bus):
    """Первый порт без drone_id резервируется под переданный drone_id."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = {
        "success": True,
        "payload": {
            "ports": [
                {"port_id": "P-01", "drone_id": "", "status": "free"},
                {"port_id": "P-02", "drone_id": "DR-9", "status": "reserved"},
            ]
        },
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


def test_request_landing_skips_occupied_ports(mock_bus):
    """Порты с непустым drone_id пропускаем, берём следующий свободный."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = {
        "ports": [
            {"port_id": "P-01", "drone_id": "DR-X", "status": "reserved"},
            {"port_id": "P-02", "drone_id": "", "status": "free"},
        ]
    }

    result = manager._handle_request_landing({"payload": {"drone_id": "DR-2"}})

    assert result == {"port_id": "P-02"}
    mock_bus.publish.assert_called_once_with(
        ComponentTopics.STATE_STORE,
        {
            "action": StateStoreActions.UPDATE_PORT,
            "payload": {
                "port_id": "P-02",
                "drone_id": "DR-2",
                "status": "reserved",
            },
        },
    )


def test_request_landing_no_free_ports_returns_error(mock_bus):
    """Все порты заняты - ошибка без publish в state_store."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = {
        "ports": [
            {"port_id": "P-01", "drone_id": "A", "status": "reserved"},
            {"port_id": "P-02", "drone_id": "B", "status": "reserved"},
        ]
    }

    result = manager._handle_request_landing({"payload": {"drone_id": "DR-1"}})

    assert result == {"error": "No free ports"}
    mock_bus.publish.assert_not_called()


def test_request_landing_state_store_none_treated_as_empty(mock_bus):
    """Ответ state_store None - список портов пустой, нет свободных мест."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = None

    result = manager._handle_request_landing({"payload": {"drone_id": "DR-1"}})

    assert result == {"error": "No free ports"}
    mock_bus.publish.assert_not_called()


def test_request_landing_missing_drone_id_returns_error(mock_bus):
    """Без валидного drone_id не ходим в state_store и не резервируем."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)

    assert manager._handle_request_landing({"payload": {}}) == {"error": "drone_id required"}
    assert manager._handle_request_landing({"payload": {"drone_id": ""}}) == {"error": "drone_id required"}
    assert manager._handle_request_landing({"payload": {"drone_id": "   "}}) == {"error": "drone_id required"}
    mock_bus.request.assert_not_called()
    mock_bus.publish.assert_not_called()


def test_request_landing_invalid_payload_type_returns_error(mock_bus):
    """payload не словарь - ошибка валидации."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)

    assert manager._handle_request_landing({"payload": []}) == {"error": "Invalid payload"}
    mock_bus.request.assert_not_called()


def test_request_landing_payload_none_is_treated_as_empty(mock_bus):
    """Если payload=None, метод преобразует его в пустой словарь и возвращает ошибку drone_id required."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)

    result = manager._handle_request_landing({"payload": None})

    # Проверяем, что пустой payload → ошибка 'drone_id required'
    assert result == {"error": "drone_id required"}

    # bus.request не вызывается, потому что drone_id нет
    mock_bus.request.assert_not_called()
    mock_bus.publish.assert_not_called()

# -------------------------
# FREE_SLOT (_handle_free_slot)
# -------------------------
def test_free_slot_publishes_free_status(mock_bus):
    """Освобождение слота - UPDATE_PORT с drone_id=None и status=free."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)

    result = manager._handle_free_slot(
        {"payload": {"port_id": "P-03", "drone_id": "DR-1"}}
    )

    assert result is None
    mock_bus.publish.assert_called_once_with(
        ComponentTopics.STATE_STORE,
        {
            "action": StateStoreActions.UPDATE_PORT,
            "payload": {
                "port_id": "P-03",
                "drone_id": None,
                "status": "free",
            },
        },
    )


def test_free_slot_missing_port_id_does_not_publish(mock_bus):
    """Без port_id не шлём UPDATE_PORT (некуда применить освобождение)."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)

    assert manager._handle_free_slot({"payload": {"drone_id": "DR-1"}}) is None
    assert manager._handle_free_slot({"payload": {"port_id": ""}}) is None
    mock_bus.publish.assert_not_called()


def test_free_slot_invalid_payload_returns_none_without_publish(mock_bus):
    """payload не dict - тихий выход без publish."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)

    assert manager._handle_free_slot({"payload": None}) is None
    mock_bus.publish.assert_not_called()

def test_free_slot_invalid_payload_type_returns_none(mock_bus):
    """payload не dict - метод тихо возвращает None и ничего не публикует."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)

    result = manager._handle_free_slot({"payload": []})
    assert result is None

    result = manager._handle_free_slot({"payload": 42})
    assert result is None

    result = manager._handle_free_slot({"payload": "oops"})
    assert result is None

    mock_bus.publish.assert_not_called()

# -------------------------
# GET_PORT_STATUS (_handle_get_port_status)
# -------------------------
def test_get_port_status_proxies_state_store_response(mock_bus):
    """Проксируем ответ GET_ALL_PORTS в поле ports."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"ports": [{"port_id": "P-03", "status": "free"}]},
    }

    result = manager._handle_get_port_status({"payload": {}})

    assert result == {"ports": [{"port_id": "P-03", "status": "free"}]}
    mock_bus.request.assert_called_once_with(
        ComponentTopics.STATE_STORE,
        {"action": StateStoreActions.GET_ALL_PORTS, "payload": {}},
        timeout=3.0,
    )


def test_get_port_status_when_store_returns_none(mock_bus):
    """state_store вернул None - отдаём пустой список портов."""
    manager = PortManager(component_id="port_manager", name="PortManager", bus=mock_bus)
    mock_bus.request.return_value = None

    result = manager._handle_get_port_status({"payload": {}})

    assert result == {"ports": []}
