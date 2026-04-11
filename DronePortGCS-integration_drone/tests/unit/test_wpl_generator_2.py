import math
import pytest
import sdk.wpl_generator_2 as gen


def _approx_point(p, q, eps=1e-10):
    return abs(p["lat"] - q["lat"]) <= eps and abs(p["lon"] - q["lon"]) <= eps and abs(p["alt"] - q["alt"]) <= eps


@pytest.fixture()
def sample_points():
    # p1: start/home, p2: bottom-left, p3: top-right
    return [
        {"lat": 55.750000, "lon": 37.610000, "alt": 60.0},
        {"lat": 55.749000, "lon": 37.611000, "alt": 60.0},
        {"lat": 55.752000, "lon": 37.616000, "alt": 80.0},
    ]


def test_rejects_non_list_root():
    with pytest.raises(ValueError, match="JSON root must be a list"):
        gen.expand_three_points_to_snake_path({"a": 1})


def test_requires_exactly_three_points():
    with pytest.raises(ValueError, match="Expected exactly 3 points"):
        gen.expand_three_points_to_snake_path([])

    with pytest.raises(ValueError, match="Expected exactly 3 points"):
        gen.expand_three_points_to_snake_path([{"lat": 0, "lon": 0, "alt": 0}] * 4)


def test_requires_fields_lat_lon_alt():
    pts = [
        {"lat": 55.75, "lon": 37.61, "alt": 60},
        {"lat": 55.749, "lon": 37.611},  # missing alt
        {"lat": 55.752, "lon": 37.616, "alt": 80},
    ]
    with pytest.raises(ValueError, match="missing required field 'alt'"):
        gen.expand_three_points_to_snake_path(pts)


def test_lat_lon_validation():
    pts = [
        {"lat": 95, "lon": 0, "alt": 0},
        {"lat": 0, "lon": 0, "alt": 0},
        {"lat": 1, "lon": 1, "alt": 0},
    ]
    with pytest.raises(ValueError, match="Latitude out of range"):
        gen.expand_three_points_to_snake_path(pts)


def test_altitude_non_negative():
    pts = [
        {"lat": 55.75, "lon": 37.61, "alt": -1},
        {"lat": 55.749, "lon": 37.611, "alt": 0},
        {"lat": 55.752, "lon": 37.616, "alt": 0},
    ]
    with pytest.raises(ValueError, match="Altitude must be >=0"):
        gen.expand_three_points_to_snake_path(pts)


def test_rectangle_geometry_requires_p3_east_and_north_of_p2(sample_points):
    # swap p2 and p3 to break geometry
    pts = [sample_points[0], sample_points[2], sample_points[1]]
    with pytest.raises(ValueError, match="p3 must be east and north of p2"):
        gen.expand_three_points_to_snake_path(pts)


def test_path_starts_at_p1_and_ends_at_p1(sample_points):
    path = gen.expand_three_points_to_snake_path(
        sample_points, line_segments=5, rect_segments_x=4, rect_segments_y=5
    )
    assert _approx_point(path[0], sample_points[0])
    assert _approx_point(path[-1], sample_points[0])


def test_path_contains_p2_and_p3(sample_points):
    path = gen.expand_three_points_to_snake_path(
        sample_points, line_segments=5, rect_segments_x=4, rect_segments_y=5
    )

    # find exact matches (since you overwrite snake[0] and snake[-1] with exact p2/p3)
    assert any(_approx_point(p, sample_points[1]) for p in path), "p2 not found in path"
    assert any(_approx_point(p, sample_points[2]) for p in path), "p3 not found in path"


def test_snake_point_count_for_column_strategy(sample_points):
    # If snake is generated as (rect_segments_x+1)*(rect_segments_y+1)
    # and we glue: leg_12 has (line_segments+1), snake[1:] adds (snake_points-1),
    # leg_31[1:] adds (line_segments) points (since leg_31 has line_segments+1)
    line_segments = 5
    rect_x = 4
    rect_y = 5

    path = gen.expand_three_points_to_snake_path(sample_points, line_segments=line_segments, rect_segments_x=rect_x, rect_segments_y=rect_y)

    snake_points = (rect_x + 1) * (rect_y + 1)
    expected_len = (line_segments + 1) + (snake_points - 1) + (line_segments)  # last leg_31[1:] has line_segments points
    assert len(path) == expected_len


def test_snake_points_are_inside_rectangle_in_local_xy(sample_points):
    path = gen.expand_three_points_to_snake_path(sample_points, line_segments=5, rect_segments_x=4, rect_segments_y=5)

    p1, p2, p3 = sample_points

    W, H = gen._ll_to_local_xy_m(p3["lat"], p3["lon"], p2["lat"], p2["lon"])

    # Extract points between p2 and p3 by finding the first occurrence of p2 and p3
    idx2 = next(i for i, p in enumerate(path) if _approx_point(p, p2))
    idx3 = next(i for i, p in enumerate(path) if _approx_point(p, p3))
    assert idx2 < idx3

    snake_segment = path[idx2: idx3 + 1]
    assert len(snake_segment) > 2

    for wp in snake_segment:
        x, y = gen._ll_to_local_xy_m(wp["lat"], wp["lon"], p2["lat"], p2["lon"])
        # Allow tiny numeric tolerance
        assert -1e-3 <= x <= W + 1e-3
        assert -1e-3 <= y <= H + 1e-3


def test_snake_has_only_axis_aligned_moves(sample_points):
    path = gen.expand_three_points_to_snake_path(sample_points, line_segments=5, rect_segments_x=4, rect_segments_y=5)

    p1, p2, p3 = sample_points

    idx2 = next(i for i, p in enumerate(path) if _approx_point(p, p2))
    idx3 = next(i for i, p in enumerate(path) if _approx_point(p, p3))

    snake_segment = path[idx2: idx3 + 1]

    # In local XY, successive points in snake should move either in x OR in y, not both
    for a, b in zip(snake_segment, snake_segment[1:]):
        ax, ay = gen._ll_to_local_xy_m(a["lat"], a["lon"], p2["lat"], p2["lon"])
        bx, by = gen._ll_to_local_xy_m(b["lat"], b["lon"], p2["lat"], p2["lon"])

        dx = abs(bx - ax)
        dy = abs(by - ay)

        assert not (dx > 1e-3 and dy > 1e-3), f"Diagonal move detected: dx={dx}, dy={dy}"


def test_points_to_wpl_header_and_line_count(sample_points):
    path = gen.expand_three_points_to_snake_path(sample_points, line_segments=5, rect_segments_x=4, rect_segments_y=5)
    wpl = gen.points_to_wpl(path, frame=gen.DEFAULT_FRAME)

    lines = [ln for ln in wpl.splitlines() if ln.strip() != ""]
    assert lines[0] == gen.WPL_HEADER
    assert len(lines) == 1 + len(path)  # header + points


def test_points_to_wpl_rejects_empty_points():
    with pytest.raises(ValueError, match="Points array is empty"):
        gen.points_to_wpl([])