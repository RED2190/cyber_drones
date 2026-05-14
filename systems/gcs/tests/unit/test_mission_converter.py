import hashlib
import pytest

from ...src.mission_converter.src import mission_converter as mission_converter_module
from ...src.mission_converter.src.mission_converter import MissionConverterComponent
from ...src.mission_converter.src.wpl_generator import points_to_wpl
from ...src.mission_converter.topics import ComponentTopics
from ...src.mission_store.topics import MissionStoreActions

@pytest.fixture
def component(mock_bus):
    return MissionConverterComponent(component_id="mission-converter", bus=mock_bus)


# -------------------------
# Тесты _extract_points
# -------------------------

def test_extract_points_returns_waypoints_list(component):
    """Проверяет, что метод возвращает список waypoints из payload."""
    payload = {"waypoints": [{"lat": 1.0, "lon": 2.0}]}
    assert component._extract_points(payload) == payload["waypoints"]


def test_extract_points_returns_empty_list_for_invalid_payload(component):
    """Проверяет, что для некорректного payload возвращается пустой список."""
    assert component._extract_points({"waypoints": "invalid"}) == []
    assert component._extract_points({}) == []


def test_extract_points_returns_empty_for_non_dict_payload(component):
    """Проверяет, что метод падает при не-словарных payload (AttributeError)."""
    with pytest.raises(AttributeError):
        component._extract_points(None)
    with pytest.raises(AttributeError):
        component._extract_points("not-a-dict")


def test_extract_points_ignores_non_dict_entries(component):
    """Проверяет, что None или некорректные точки в списке игнорируются."""
    payload = {"waypoints": [{"lat": 1, "lon": 2}, None, 123, {"lat": 3, "lon": 4}]}
    points = component._extract_points(payload)
    assert points == payload["waypoints"]


# -------------------------
# Тесты _to_wpl
# -------------------------

def test_to_wpl_formats_header_and_waypoints(component):
    """Проверяет, что WPL формируется с корректным заголовком и строками точек."""
    points = [
        {"lat": 55.1, "lon": 37.2, "alt_m": 100},
        {"lat": 55.2, "lon": 37.3, "alt_m": 110},
        {"lat": 55.3, "lon": 37.4, "alt_m": 120},
        {"lat": 55.4, "lon": 37.5, "alt_m": 130},
    ]
    result = component._to_wpl(points)
    lines = result.splitlines()
    assert lines[0] == "QGC WPL 110"
    assert lines[1] == "0\t1\t3\t16\t0\t0\t0\t0\t55.1\t37.2\t0.0\t1"
    assert lines[2] == "1\t0\t3\t16\t0\t0\t0\t0\t55.2\t37.3\t0.0\t1"


def test_to_wpl_with_empty_points_returns_only_header(component):
    """Проверяет, что пустой список точек возвращает только заголовок WPL."""
    result = component._to_wpl([])
    assert result == "QGC WPL 110"


def test_to_wpl_uses_defaults_for_missing_fields(component):
    """Проверяет, что отсутствующие поля в точках подставляются дефолтами."""
    points = [{}]
    result = component._to_wpl(points)
    expected_line = "0\t1\t3\t16\t0\t0\t0\t0\t0.0\t0.0\t0.0\t1"
    assert result.splitlines() == ["QGC WPL 110", expected_line]


def test_to_wpl_with_partial_params(component):
    """Проверяет корректную подстановку частичных params в WPL."""
    points = [{"lat": 10, "lon": 20, "alt": 5, "params": {"p2": 7}}]
    result = component._to_wpl(points)
    assert "0\t1\t3\t16\t0\t7\t0\t0\t10\t20\t5\t1" in result


def test_to_wpl_with_none_and_empty_points(component):
    """Проверяет обработку None и пустых точек: игнорируются и не ломают WPL."""
    points = [None, {}]
    result = component._to_wpl(points)
    lines = result.splitlines()
    assert lines[1] == "1\t0\t3\t16\t0\t0\t0\t0\t0.0\t0.0\t0.0\t1"


def test_to_wpl_with_high_precision_floats(component):
    """Проверяет, что WPL корректно сохраняет высокоточние float значения."""
    points = [{"lat": 55.123456789, "lon": 37.987654321, "alt": 100.123456}]
    wpl = component._to_wpl(points)
    assert "55.123456789" in wpl
    assert "37.987654321" in wpl
    assert "100.123456" in wpl


def test_points_to_wpl_skips_non_dict_entries():
    result = points_to_wpl([None, {"lat": 1.0, "lon": 2.0, "alt_m": 3.0}])
    lines = result.splitlines()
    assert lines[0] == "QGC WPL 110"
    assert lines[1] == "1\t0\t3\t16\t0\t0\t0\t0\t1.0\t2.0\t3.0\t1"


# -------------------------
# Тесты _handle_mission_prepare
# -------------------------

def test_handle_mission_prepare_returns_wpl_and_signature(component, mock_bus):
    """Проверяет формирование WPL для миссии через текущий конвертер."""
    mission = {
        "waypoints": [
            {"lat": 10.0, "lon": 20.0, "alt_m": 30.0},
            {"lat": 11.0, "lon": 21.0, "alt_m": 31.0},
        ]
    }
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": mission},
    }
    result = component._handle_mission_prepare({"payload": {"mission_id": "m-1"}, "correlation_id": "corr-1"})

    expected_wpl = points_to_wpl(mission["waypoints"]).rstrip("\n")
    assert result == {
        "mission": {
            "mission_id": "m-1",
            "wpl": expected_wpl,
        },
        "from": "mission-converter",
    }
    mock_bus.request.assert_called_once_with(
        ComponentTopics.MISSION_STORE,
        {
            "action": MissionStoreActions.GET_MISSION,
            "sender": "mission-converter",
            "payload": {"mission_id": "m-1"},
            "correlation_id": "corr-1",
        },
        timeout=10.0,
    )


def test_handle_mission_prepare_returns_error_when_store_unavailable(component, mock_bus):
    """Проверяет возврат ошибки, если MissionStore недоступен (None)."""
    mock_bus.request.return_value = None
    result = component._handle_mission_prepare({"payload": {"mission_id": "m-404"}})
    assert result == {"error": "mission store unavailable", "from": "mission-converter"}


def test_handle_mission_prepare_returns_error_when_store_returns_failure(component, mock_bus):
    """Проверяет возврат ошибки, если MissionStore вернул success=False."""
    mock_bus.request.return_value = {"success": False, "payload": {}}
    result = component._handle_mission_prepare({"payload": {"mission_id": "m-500"}})
    assert result == {"error": "mission store unavailable", "from": "mission-converter"}


def test_handle_mission_prepare_returns_error_when_mission_id_missing(component, mock_bus):
    """Проверяет обработку случая, когда mission_id отсутствует в payload."""
    mock_bus.request.return_value = None
    result = component._handle_mission_prepare({"payload": {}})
    assert result == {"error": "mission store unavailable", "from": "mission-converter"
    }


def test_handle_mission_prepare_returns_error_when_store_payload_missing_mission(component, mock_bus):
    """Если store вернул success=True, но без ключа 'mission', компонент не падает и возвращает WPL-заголовок."""
    mock_bus.request.return_value = {"success": True, "payload": {}}
    result = component._handle_mission_prepare({"payload": {"mission_id": "m-missing"}})
    assert result == {
        "mission": {"mission_id": "m-missing", "wpl": "QGC WPL 110"},
        "from": "mission-converter",
    }


def test_handle_mission_prepare_passes_mission_id_to_store(component, mock_bus):
    mock_bus.request.return_value = {"success": True, "payload": {"mission": {"waypoints": []}}}

    result = component._handle_mission_prepare({"payload": {"mission_id": "m-42"}})

    mock_bus.request.assert_called_once_with(
        ComponentTopics.MISSION_STORE,
        {
            "action": MissionStoreActions.GET_MISSION,
            "sender": "mission-converter",
            "payload": {"mission_id": "m-42"},
        },
        timeout=10.0,
    )
    assert result["mission"]["mission_id"] == "m-42"


def test_handle_mission_prepare_returns_wpl_header_when_mission_has_no_waypoints(component, mock_bus):
    """Проверяет формирование WPL только с заголовком, если waypoints пустые или отсутствуют."""
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": {}},
    }
    result = component._handle_mission_prepare({"payload": {"mission_id": "m-empty"}})
    assert result == {
        "mission": {"mission_id": "m-empty", "wpl": "QGC WPL 110"},
        "from": "mission-converter",
    }


def test_handle_mission_prepare_wpl_changes_on_waypoints(component, mock_bus):
    waypoints1 = [{"lat": 1, "lon": 2, "alt": 3}]
    waypoints2 = [{"lat": 1, "lon": 2, "alt": 4}]

    mock_bus.request.side_effect = [
        {"success": True, "payload": {"mission": {"waypoints": waypoints1}}},
        {"success": True, "payload": {"mission": {"waypoints": waypoints2}}},
    ]

    result1 = component._handle_mission_prepare({"payload": {"mission_id": "m-1"}})
    result2 = component._handle_mission_prepare({"payload": {"mission_id": "m-1"}})
    assert result1["mission"]["wpl"] != result2["mission"]["wpl"]


def test_handle_mission_prepare_with_empty_mission_id(component, mock_bus):
    """Проверяет корректную обработку пустого mission_id."""
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": {"waypoints": []}},
    }

    result = component._handle_mission_prepare({"payload": {"mission_id": ""}})

    assert result["mission"]["mission_id"] == ""


def test_handle_mission_prepare_falls_back_to_local_to_wpl_on_generator_error(component, mock_bus, monkeypatch):
    mission = {"waypoints": [{"lat": 10.0, "lon": 20.0, "alt": 30.0}]}
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": mission},
    }

    def fail_generator(points):
        raise ValueError("broken generator")

    monkeypatch.setattr(mission_converter_module, "points_to_wpl", fail_generator)

    result = component._handle_mission_prepare({"payload": {"mission_id": "m-fallback"}})

    assert result == {
        "mission": {
            "mission_id": "m-fallback",
            "wpl": component._to_wpl(mission["waypoints"]),
        },
        "from": "mission-converter",
    }


def test_handle_mission_prepare_raises_on_invalid_payload_type(component):
    """Проверяет, что AttributeError вызывается при некорректном типе payload."""
    with pytest.raises(AttributeError):
        component._handle_mission_prepare(None)
    with pytest.raises(AttributeError):
        component._handle_mission_prepare({"payload": []})
