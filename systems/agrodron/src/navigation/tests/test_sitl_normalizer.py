"""Тесты для sitl_normalizer."""
from systems.agrodron.src.navigation.src.sitl_normalizer import normalize_sitl_to_nav_state


def test_sitl_position_v1():
    """Формат sitl.position.v1: drone_id, lat, lon, alt, vx."""
    raw = {
        "drone_id": "drone_001",
        "lat": 59.9386,
        "lon": 30.3165,
        "alt": 100.2,
        "vx": 1.23,
    }
    result = normalize_sitl_to_nav_state(raw)
    assert result["lat"] == 59.9386
    assert result["lon"] == 30.3165
    assert result["alt_m"] == 100.2
    assert result["ground_speed_mps"] == 1.23
    assert result["drone_id"] == "drone_001"
    assert result["gps_valid"] is True


def test_redis_state():
    """Формат Redis (drone:{id}:state): lat, lon, alt, vx, vy, vz, heading."""
    raw = {
        "lat": 59.938623,
        "lon": 30.316534,
        "alt": 100.0,
        "vx": 1.23,
        "vy": 0.87,
        "vz": 0.0,
        "heading": 25.8,
        "status": "MOVING",
        "last_update": "2026-03-08T16:40:00Z",
    }
    result = normalize_sitl_to_nav_state(raw)
    assert result["lat"] == 59.938623
    assert result["lon"] == 30.316534
    assert result["alt_m"] == 100.0
    assert abs(result["ground_speed_mps"] - (1.23**2 + 0.87**2) ** 0.5) < 0.01
    assert result["heading_deg"] == 25.8
    assert result["timestamp"] == "2026-03-08T16:40:00Z"
    assert result["gps_valid"] is True


def test_nmea_derived():
    """Формат NMEA-derived: derived + nmea."""
    raw = {
        "derived": {
            "lat_decimal": 60.12345,
            "lon_decimal": 30.12340,
            "altitude_msl": 4.9,
        },
        "nmea": {
            "rmc": {"speed_knots": 9.3, "course_degrees": 90.0},
            "gga": {"quality": 1, "satellites": 14, "hdop": 0.7},
        },
    }
    result = normalize_sitl_to_nav_state(raw)
    assert result["lat"] == 60.12345
    assert result["lon"] == 30.12340
    assert result["alt_m"] == 4.9
    assert abs(result["ground_speed_mps"] - 9.3 * 0.514444) < 0.01
    assert result["heading_deg"] == 90.0
    assert result["satellites"] == 14
    assert result["hdop"] == 0.7
    assert result["fix"] == "3D"
    assert result["gps_valid"] is True


def test_passthrough_already_normalized():
    """Pass-through: данные уже в формате NAV_STATE."""
    raw = {
        "lat": 60.12345,
        "lon": 30.12340,
        "alt_m": 4.9,
        "ground_speed_mps": 4.8,
        "heading_deg": 90.0,
        "fix": "3D",
        "satellites": 14,
        "hdop": 0.7,
    }
    result = normalize_sitl_to_nav_state(raw)
    assert result["lat"] == 60.12345
    assert result["lon"] == 30.12340
    assert result["alt_m"] == 4.9
    assert result["ground_speed_mps"] == 4.8
    assert result["heading_deg"] == 90.0
    assert result["fix"] == "3D"
    assert result["satellites"] == 14
    assert result["hdop"] == 0.7
    assert result["gps_valid"] is True


def test_invalid_input():
    """Невалидный/пустой ввод."""
    assert normalize_sitl_to_nav_state(None)["lat"] == 0.0
    assert normalize_sitl_to_nav_state({})["lat"] == 0.0
