"""
Нормализатор данных от SITL-адаптера в формат NAV_STATE.

Поддерживает форматы:
- sitl.position.v1: {"drone_id","lat","lon","alt","vx"}
- Redis (drone:{id}:state): lat, lon, alt, vx, vy, vz, heading, status
- Redis (SITL:{drone_id}): {"data":{...},"verifier_stage":"SITL-v1"} — новый формат
- NMEA-derived: derived.lat_decimal, nmea.gga и т.п.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict


def _float_val(obj: Any, key: str, default: float = 0.0) -> float:
    try:
        val = obj.get(key) if isinstance(obj, dict) else None
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _int_val(obj: Any, key: str, default: int = 0) -> int:
    try:
        val = obj.get(key) if isinstance(obj, dict) else None
        return int(float(val)) if val is not None else default
    except (TypeError, ValueError):
        return default


def normalize_sitl_to_nav_state(raw: Dict[str, Any], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Преобразует сырой ответ SITL-адаптера в единый формат NAV_STATE.

    Входные форматы:
    - sitl.position.v1: {drone_id, lat, lon, alt, vx}
    - Redis-state: {lat, lon, alt, vx, vy, vz, heading, status}
    - NMEA-derived: {derived: {...}, nmea: {rmc, gga}}
    """
    result: Dict[str, Any] = {
        "lat": 0.0,
        "lon": 0.0,
        "alt_m": 0.0,
        "ground_speed_mps": 0.0,
        "heading_deg": 0.0,
        "fix": "NONE",
        "satellites": 0,
        "hdop": 99.9,
        "gps_valid": False,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    if not isinstance(raw, dict):
        return result

    # --- SITL Redis новый формат: {data: {...}, verifier_stage: "SITL-v1"} ---
    if raw.get("verifier_stage") == "SITL-v1" or raw.get("core_stage") == "SITL-v1":
        inner = raw.get("data") or raw
        if isinstance(inner, dict):
            derived = inner.get("derived") or {}
            if isinstance(derived, dict):
                result["lat"] = _float_val(derived, "lat_decimal")
                result["lon"] = _float_val(derived, "lon_decimal")
                result["alt_m"] = _float_val(derived, "altitude_msl")
            result["lat"] = result["lat"] or _float_val(inner, "lat")
            result["lon"] = result["lon"] or _float_val(inner, "lon")
            result["alt_m"] = result["alt_m"] or _float_val(inner, "alt", _float_val(inner, "altitude_msl", 0.0))
            vx = _float_val(inner, "vx")
            vy = _float_val(inner, "vy")
            result["ground_speed_mps"] = math.sqrt(vx * vx + vy * vy) if (vx or vy) else 0.0
            result["heading_deg"] = _float_val(inner, "heading") or (
                (math.degrees(math.atan2(vx, vy)) + 360.0) % 360.0 if (vx or vy) else 0.0
            )
            if inner.get("drone_id"):
                result["drone_id"] = str(inner["drone_id"])
            result["gps_valid"] = result["lat"] != 0 or result["lon"] != 0
            return result

    # --- Pass-through: уже в формате NAV_STATE (alt_m, heading_deg, ground_speed_mps) ---
    if "alt_m" in raw or "ground_speed_mps" in raw or "heading_deg" in raw:
        for key in ("lat", "lon", "alt_m", "ground_speed_mps", "heading_deg", "fix", "satellites", "hdop", "drone_id", "timestamp"):
            if key in raw and raw[key] is not None:
                if key in ("lat", "lon", "alt_m", "ground_speed_mps", "heading_deg", "hdop"):
                    result[key] = _float_val(raw, key)
                elif key == "satellites":
                    result[key] = _int_val(raw, key)
                else:
                    result[key] = raw[key]
        result["gps_valid"] = (
            result["fix"] == "3D"
            and result["satellites"] >= 4
            and result["hdop"] < 10.0
        )
        return result

    # --- sitl.position.v1: drone_id, lat, lon, alt, vx ---
    if "lat" in raw and "lon" in raw:
        result["lat"] = _float_val(raw, "lat")
        result["lon"] = _float_val(raw, "lon")
        result["alt_m"] = _float_val(raw, "alt", _float_val(raw, "altitude_msl", 0.0))
        vx = _float_val(raw, "vx")
        vy = _float_val(raw, "vy")
        result["ground_speed_mps"] = math.sqrt(vx * vx + vy * vy) if vy != 0 else abs(vx)
        result["heading_deg"] = _float_val(raw, "heading")
        if raw.get("drone_id"):
            result["drone_id"] = str(raw["drone_id"])
        if raw.get("last_update"):
            result["timestamp"] = str(raw["last_update"])

    # --- NMEA-derived: derived + nmea ---
    derived = raw.get("derived") or {}
    nmea = raw.get("nmea") or {}
    if isinstance(derived, dict) and (derived.get("lat_decimal") is not None or derived.get("lon_decimal") is not None):
        result["lat"] = _float_val(derived, "lat_decimal")
        result["lon"] = _float_val(derived, "lon_decimal")
        result["alt_m"] = _float_val(derived, "altitude_msl")

    rmc = nmea.get("rmc") or {}
    gga = nmea.get("gga") or {}
    if isinstance(rmc, dict):
        if rmc.get("course_degrees") is not None:
            result["heading_deg"] = _float_val(rmc, "course_degrees")
        knots = _float_val(rmc, "speed_knots")
        if knots is not None and knots != 0:
            result["ground_speed_mps"] = knots * 0.514444  # knots to m/s
    if isinstance(gga, dict):
        result["satellites"] = _int_val(gga, "satellites")
        result["hdop"] = _float_val(gga, "hdop", 99.9)
        quality = _int_val(gga, "quality")
        result["fix"] = "3D" if quality >= 1 and result["satellites"] >= 4 else "2D" if quality >= 1 else "NONE"

    # --- Качество GPS ---
    nmea_root = raw.get("nmea") if isinstance(raw.get("nmea"), dict) else {}
    gga_block = nmea_root.get("gga") if isinstance(nmea_root, dict) else None
    has_gga = isinstance(gga_block, dict) and bool(gga_block)

    result["gps_valid"] = (
        result["fix"] == "3D"
        and result["satellites"] >= 4
        and result["hdop"] < 10.0
    )
    # Ответ SITL из Redis (lat/lon/alt без NMEA): строгие критерии выше дают gps_valid=False,
    # хотя координаты есть — для навигации считаем их валидными, не трогая SITL.
    if not result["gps_valid"] and not has_gga:
        derived_raw = raw.get("derived") if isinstance(raw.get("derived"), dict) else {}
        has_position_source = ("lat" in raw and "lon" in raw) or (
            derived_raw.get("lat_decimal") is not None or derived_raw.get("lon_decimal") is not None
        )
        if has_position_source:
            la, lo = result["lat"], result["lon"]
            if abs(la) <= 90.0 and abs(lo) <= 180.0:
                result["gps_valid"] = True

    if raw.get("drone_id") and "drone_id" not in result:
        result["drone_id"] = str(raw["drone_id"])
    if raw.get("timestamp"):
        result["timestamp"] = str(raw["timestamp"])

    return result
