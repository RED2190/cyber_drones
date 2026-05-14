"""Локальные функции генерации маршрута для PathPlanner."""

from __future__ import annotations

from typing import Any, Dict, List


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def expand_two_points_to_path(
    seed_points: List[Dict[str, Any]],
    *,
    cruise_alt_m: float = 50.0,
    num_intermediates: int = 4,
) -> List[Dict[str, float]]:
    """Расширяет две seed-точки в маршрут со взлетом, крейсером и посадкой."""
    if len(seed_points) != 2:
        raise ValueError("need exactly 2 seed points")

    start, end = seed_points[0], seed_points[1]
    alt_key = "alt_m" if "alt_m" in start else "alt"
    start_alt = float(start.get(alt_key, 0))
    end_alt = float(end.get(alt_key, 0))

    route: List[Dict[str, float]] = []

    route.append({
        "lat": start["lat"],
        "lon": start["lon"],
        "alt_m": start_alt,
    })
    route.append({
        "lat": start["lat"],
        "lon": start["lon"],
        "alt_m": cruise_alt_m,
    })

    for i in range(1, num_intermediates + 1):
        t = i / (num_intermediates + 1)
        route.append({
            "lat": round(_lerp(start["lat"], end["lat"], t), 7),
            "lon": round(_lerp(start["lon"], end["lon"], t), 7),
            "alt_m": cruise_alt_m,
        })

    route.append({
        "lat": end["lat"],
        "lon": end["lon"],
        "alt_m": cruise_alt_m,
    })
    route.append({
        "lat": end["lat"],
        "lon": end["lon"],
        "alt_m": end_alt,
    })

    return route


def expand_three_points_to_snake_path(
    seed_points: List[Dict[str, Any]],
    *,
    num_passes: int = 3,
    cruise_alt_m: float = 50.0,
) -> List[Dict[str, float]]:
    """Строит зигзагообразный маршрут по трём seed-точкам."""
    if len(seed_points) != 3:
        raise ValueError("need exactly 3 seed points")

    p1, p2, p3 = seed_points[0], seed_points[1], seed_points[2]
    alt_key = "alt_m" if "alt_m" in p1 else "alt"
    alt = float(p1.get(alt_key, cruise_alt_m)) or cruise_alt_m

    route: List[Dict[str, float]] = []

    for i in range(num_passes):
        t = i / max(num_passes - 1, 1)

        row_start_lat = _lerp(p1["lat"], p3["lat"], t)
        row_start_lon = _lerp(p1["lon"], p3["lon"], t)
        row_end_lat = _lerp(p2["lat"], p3["lat"], t)
        row_end_lon = _lerp(p2["lon"], p3["lon"], t)

        if i % 2 == 0:
            route.append({"lat": round(row_start_lat, 7), "lon": round(row_start_lon, 7), "alt_m": alt})
            route.append({"lat": round(row_end_lat, 7), "lon": round(row_end_lon, 7), "alt_m": alt})
        else:
            route.append({"lat": round(row_end_lat, 7), "lon": round(row_end_lon, 7), "alt_m": alt})
            route.append({"lat": round(row_start_lat, 7), "lon": round(row_start_lon, 7), "alt_m": alt})

    return route
