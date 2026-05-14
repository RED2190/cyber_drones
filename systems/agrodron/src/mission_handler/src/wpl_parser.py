"""
Парсер файлов миссий в формате WPL (QGC WPL / ArduPilot Waypoint).

Формат WPL — текстовый, табуляция между колонками.
Колонки: Index, Current, Frame, Command, P1, P2, P3, P4, Lat, Lon, Alt, Autocontinue
MAV_CMD 16 = NAV_WAYPOINT.
"""
from typing import Any, Dict, List, Optional, Tuple


# MAV_CMD_NAV_WAYPOINT
MAV_CMD_NAV_WAYPOINT = 16

# Индексы колонок в строке WPL (0-based)
COL_INDEX = 0
COL_CURRENT = 1
COL_FRAME = 2
COL_COMMAND = 3
COL_P1 = 4
COL_P2 = 5
COL_P3 = 6
COL_P4 = 7
COL_LAT = 8
COL_LON = 9
COL_ALT = 10
COL_AUTOCONTINUE = 11


def parse_wpl(wpl_content: str, mission_id: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Парсит содержимое WPL-файла и преобразует в JSON-формат автопилота.

    Args:
        wpl_content: Сырое содержимое WPL-файла (строка).
        mission_id: Опциональный ID миссии. Если не задан — генерируется.

    Returns:
        Кортеж (mission_dict, error).
        При успехе: (dict, None).
        При ошибке: (None, "описание_ошибки").
    """
    if not wpl_content or not isinstance(wpl_content, str):
        return None, "empty_or_invalid_wpl"

    lines = [line.strip() for line in wpl_content.strip().splitlines() if line.strip()]
    if not lines:
        return None, "empty_wpl"

    # Первая строка — заголовок (QGC WPL 110 и т.п.)
    header = lines[0].upper()
    if not header.startswith("QGC WPL"):
        return None, "invalid_wpl_header"

    waypoints: List[Dict[str, Any]] = []
    home: Optional[Dict[str, float]] = None

    for i, line in enumerate(lines[1:], start=1):
        parts = line.split("\t")
        if len(parts) < 12:
            # Попытка разбора по пробелам (некоторые экспорты используют пробелы)
            parts = line.split()
        if len(parts) < 12:
            return None, f"invalid_wpl_line_{i}_too_few_columns"

        try:
            idx = int(float(parts[COL_INDEX]))
            cmd = int(float(parts[COL_COMMAND]))
            lat = float(parts[COL_LAT])
            lon = float(parts[COL_LON])
            alt = float(parts[COL_ALT])
        except (ValueError, IndexError):
            return None, f"invalid_wpl_line_{i}_parse_error"

        # HOME (index -1) или NAV_WAYPOINT (16)
        if idx == -1:
            home = {"lat": lat, "lon": lon, "alt_m": alt}
            continue
        if cmd != MAV_CMD_NAV_WAYPOINT:
            # Пропускаем служебные команды (TAKEOFF, LAND и т.п.)
            # При необходимости можно добавить поддержку.
            continue

        step: Dict[str, Any] = {
            "id": f"wp-{len(waypoints):03d}",
            "lat": lat,
            "lon": lon,
            "alt_m": alt,
            "speed_mps": 5.0,
            "spray": False,
        }
        waypoints.append(step)

    if not waypoints:
        return None, "no_waypoints_in_wpl"

    if home is None and waypoints:
        first = waypoints[0]
        home = {"lat": first["lat"], "lon": first["lon"], "alt_m": 0.0}

    mid = mission_id
    if not mid:
        import time
        mid = f"wpl-{int(time.time() * 1000)}"

    mission: Dict[str, Any] = {
        "mission_id": mid,
        "home": home or {"lat": 0.0, "lon": 0.0, "alt_m": 0.0},
        "steps": waypoints,
    }
    return mission, None
