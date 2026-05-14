"""Локальная генерация WPL для MissionConverter."""

from __future__ import annotations

from typing import Any, Dict


def points_to_wpl(points: list[Dict[str, Any]]) -> str:
    lines = ["QGC WPL 110"]

    for idx, point in enumerate(points):
        if not isinstance(point, dict):
            continue

        lat = point.get("lat", point.get("latitude", 0.0))
        lon = point.get("lon", point.get("lng", point.get("longitude", 0.0)))
        alt = point.get("alt", point.get("alt_m", point.get("altitude", 0.0)))
        params = point.get("params", {})

        line = "\t".join(
            [
                str(idx),
                "1" if idx == 0 else "0",
                str(point.get("frame", 3)),
                str(point.get("command", 16)),
                str(params.get("p1", 0)),
                str(params.get("p2", 0)),
                str(params.get("p3", 0)),
                str(params.get("p4", 0)),
                str(lat),
                str(lon),
                str(alt),
                "1",
            ]
        )
        lines.append(line)

    return "\n".join(lines)
