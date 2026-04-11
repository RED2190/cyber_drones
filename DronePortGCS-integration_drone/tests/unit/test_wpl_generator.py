import pytest
import json

from sdk.wpl_generator import (
    points_to_wpl,
    json_to_wpl,
    expand_two_points_to_path,
)

def _assert_point_xyz(a, b, tol=1e-9):
    assert abs(a["lat"] - b["lat"]) <= tol
    assert abs(a["lon"] - b["lon"]) <= tol
    assert abs(a["alt"] - b["alt"]) <= tol


def test_expand_two_points_segments_5_produces_closed_cycle():
    start = {"lat": 10, "lon": 20, "alt": 50}
    end = {"lat": 20, "lon": 40, "alt": 150}

    path = expand_two_points_to_path([start, end], segments=5)
    assert len(path) == 11
    _assert_point_xyz(path[0], {"lat": 10.0, "lon": 20.0, "alt": 50.0})
    _assert_point_xyz(path[5], {"lat": 20.0, "lon": 40.0, "alt": 150.0})
    _assert_point_xyz(path[-1], {"lat": 10.0, "lon": 20.0, "alt": 50.0})
    _assert_point_xyz(path[1], {"lat": 12.0, "lon": 24.0, "alt": 70.0})

    for i in range(len(path)):
        _assert_point_xyz(path[i], path[-1 - i])


def test_expand_two_points_params_policy_start_mid_end():
    start = {"lat": 0, "lon": 0, "alt": 10}
    end = {"lat": 10, "lon": 10, "alt": 20}

    path = expand_two_points_to_path([start, end], segments=5)
    assert len(path) == 11

    assert path[0]["param1"] == 0.0
    assert path[0]["param2"] == 0.0
    assert path[0]["param3"] == 0.0
    assert path[0]["param4"] == 0.0

    assert path[1]["param1"] == 0.0
    assert path[1]["param2"] == 0.0
    assert path[1]["param3"] == 0.0
    assert path[1]["param4"] == 0.0

    assert path[5]["param1"] == 0.0
    assert path[5]["param2"] == 0.0
    assert path[5]["param3"] == 0.0
    assert path[5]["param4"] == 0.0

    _assert_point_xyz(path[-2], path[1])
    assert path[-2]["param1"] == 0.0
    assert path[-2]["param2"] == 0.0
    assert path[-2]["param3"] == 0.0
    assert path[-2]["param4"] == 0.0


def test_expand_requires_exactly_two_points():
    with pytest.raises(ValueError, match="exactly 2 points"):
        expand_two_points_to_path([], segments=5)

    with pytest.raises(ValueError, match="exactly 2 points"):
        expand_two_points_to_path(
            [{"lat": 0, "lon": 0, "alt": 1}],
            segments=5,
        )

    with pytest.raises(ValueError, match="exactly 2 points"):
        expand_two_points_to_path([{}, {}, {}], segments=5)


def test_expand_segments_must_be_positive():
    start = {"lat": 0, "lon": 0, "alt": 10}
    end = {"lat": 1, "lon": 1, "alt": 10}

    with pytest.raises(ValueError, match="Segments"):
        expand_two_points_to_path([start, end], segments=0)


def test_expand_start_and_end_must_be_different():
   
    start = {"lat": 59.9, "lon": 30.3, "alt": 50}
    end = {"lat": 59.9, "lon": 30.3, "alt": 100}

    with pytest.raises(ValueError, match="Start and end points must be different"):
        expand_two_points_to_path([start, end], segments=5)


def test_expand_allows_missing_command_params_and_uses_defaults():
    start = {"lat": 0, "lon": 0, "alt": 10}
    end = {"lat": 1, "lon": 1, "alt": 10}

    path = expand_two_points_to_path([start, end], segments=5)

    assert path[0]["param1"] == 0.0
    assert path[0]["param2"] == 0.0
    assert path[0]["param3"] == 0.0
    assert path[0]["param4"] == 0.0


@pytest.mark.parametrize(
    "which, field, value, error",
    [
        ("start", "lat", 999, "Latitude out of range"),
        ("start", "lon", 999, "Longitude out of range"),
        ("end", "lat", 999, "Latitude out of range"),
        ("end", "lon", 999, "Longitude out of range"),
    ],
)
def test_expand_invalid_coordinates_raise(which, field, value, error):
    start = {"lat": 0, "lon": 0, "alt": 10}
    end = {"lat": 10, "lon": 10, "alt": 20}

    if which == "start":
        start[field] = value
    else:
        end[field] = value

    with pytest.raises(ValueError, match=error):
        expand_two_points_to_path([start, end], segments=5)


def test_expand_negative_alt_raises():
    start = {"lat": 0, "lon": 0, "alt": 10}
    end = {"lat": 10, "lon": 10, "alt": -1}

    with pytest.raises(ValueError, match="Altitude must be >=0"):
        expand_two_points_to_path([start, end], segments=5)


def test_expand_start_or_end_not_dict_raises():
    start = {"lat": 0, "lon": 0, "alt": 10}
    with pytest.raises(ValueError, match="must be dict objects"):
        expand_two_points_to_path([start, 123], segments=5)


def test_points_to_wpl_successful_generation_cycle_11_points():

    points = [
        {"lat": 1, "lon": 2, "alt": 3, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 4, "lon": 5, "alt": 6, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 7, "lon": 8, "alt": 9, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 10, "lon": 11, "alt": 12, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 13, "lon": 14, "alt": 15, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 16, "lon": 17, "alt": 18, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 13, "lon": 14, "alt": 15, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 10, "lon": 11, "alt": 12, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 7, "lon": 8, "alt": 9, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 4, "lon": 5, "alt": 6, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 1, "lon": 2, "alt": 3, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
    ]

    wpl = points_to_wpl(points, frame=3)
    assert wpl.startswith("QGC WPL 110\n")

    lines = wpl.strip().splitlines()
    assert len(lines) == 1 + 11  
    assert lines[0] == "QGC WPL 110"

    for idx in range(1, 12):
        fields = lines[idx].split("\t")
        assert len(fields) == 12

    fields0 = lines[1].split("\t")
    fields1 = lines[2].split("\t")
    assert fields0[1] == "1"
    assert fields1[1] == "0"

    assert fields0[2] == "3"
    assert fields0[3] == "16"
    assert fields0[11] == "1"


def test_points_to_wpl_empty_points_raises():
    with pytest.raises(ValueError, match="Points array is empty"):
        points_to_wpl([], frame=3)


@pytest.mark.parametrize("missing_field", ["lat", "lon", "alt"])
def test_points_to_wpl_missing_required_fields(missing_field):
    point = {
        "lat": 59.9,
        "lon": 30.3,
        "alt": 80,
        "param1": 0,
        "param2": 5,
        "param3": 0,
        "param4": 0,
    }

    del point[missing_field]

    with pytest.raises(ValueError, match=f"missing required field '{missing_field}'"):
        points_to_wpl([point])


@pytest.mark.parametrize("param_field", ["param1", "param2", "param3", "param4"])
def test_points_to_wpl_param_fields_must_be_numbers(param_field):
    point = {
        "lat": 59.9,
        "lon": 30.3,
        "alt": 80,
        "param1": 0,
        "param2": 5,
        "param3": 0,
        "param4": 0,
    }
    point[param_field] = "oops"

    with pytest.raises(ValueError, match=f"Field '{param_field}' must be a number"):
        points_to_wpl([point], frame=3)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("lat", 999, "Latitude out of range"),
        ("lon", 999, "Longitude out of range"),
    ],
)
def test_points_to_wpl_invalid_coordinates(field, value, error):
    point = {
        "lat": 59.9,
        "lon": 30.3,
        "alt": 80,
        "param1": 0,
        "param2": 5,
        "param3": 0,
        "param4": 0,
    }

    point[field] = value

    with pytest.raises(ValueError, match=error):
        points_to_wpl([point], frame=3)


def test_points_to_wpl_negative_alt_raises():
    points = [{"lat": 59.9, "lon": 30.3, "alt": -1, "param1": 0, "param2": 5, "param3": 0, "param4": 0}]
    with pytest.raises(ValueError, match="Altitude must be >=0"):
        points_to_wpl(points, frame=3)


def test_json_to_wpl_file_created_and_has_expected_lines(tmp_path):
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.wpl"

    points = [
        {"lat": 59.9, "lon": 30.3, "alt": 50},
        {"lat": 59.8, "lon": 30.2, "alt": 100},
    ]
    input_file.write_text(json.dumps(points), encoding="utf-8")

    json_to_wpl(str(input_file), str(output_file), frame=3, segments=5)

    assert output_file.exists()
    assert output_file.stat().st_size > 0

    content = output_file.read_text(encoding="utf-8")
    assert content.startswith("QGC WPL 110\n")

    lines = content.strip().splitlines()
    assert len(lines) == 1 + 11
    fields0 = lines[1].split("\t")
    assert fields0[2] == "3"
    assert fields0[3] == "16"


def test_json_to_wpl_interpolates_20_percent_point(tmp_path):
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.wpl"

    points = [
        {"lat": 10, "lon": 20, "alt": 50},
        {"lat": 20, "lon": 40, "alt": 150},
    ]
    input_file.write_text(json.dumps(points), encoding="utf-8")

    json_to_wpl(str(input_file), str(output_file), frame=3, segments=5)

    lines = output_file.read_text(encoding="utf-8").strip().splitlines()
    fields = lines[2].split("\t")

    assert fields[8] == "12.0"
    assert fields[9] == "24.0"
    assert fields[10] == "70.0"
    assert fields[7] == "0.0"


def test_json_to_wpl_input_file_not_found_raises(tmp_path):
    missing_input = tmp_path / "missing.json"
    output_file = tmp_path / "out.wpl"
    with pytest.raises(FileNotFoundError, match="Input file not found"):
        json_to_wpl(str(missing_input), str(output_file), frame=3, segments=5)


def test_json_to_wpl_output_path_not_writable_raises(tmp_path):
    input_file = tmp_path / "input.json"
    bad_output = tmp_path / "no_such_dir" / "out.wpl"

    points = [
        {"lat": 59.9, "lon": 30.3, "alt": 50, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
        {"lat": 59.8, "lon": 30.2, "alt": 100, "param1": 0, "param2": 5, "param3": 0, "param4": 0},
    ]
    input_file.write_text(json.dumps(points), encoding="utf-8")

    with pytest.raises(OSError):
        json_to_wpl(str(input_file), str(bad_output), frame=3, segments=5)


def test_json_to_wpl_invalid_json_raises(tmp_path):
    input_file = tmp_path / "bad.json"
    output_file = tmp_path / "out.wpl"

    input_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        json_to_wpl(str(input_file), str(output_file), frame=3, segments=5)


def test_json_to_wpl_json_root_not_list_raises(tmp_path):
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "out.wpl"

    input_file.write_text(json.dumps({"a": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON root must be a list of points"):
        json_to_wpl(str(input_file), str(output_file), frame=3, segments=5)


def test_json_to_wpl_list_not_two_points_raises(tmp_path):
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "out.wpl"

    input_file.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected exactly 2 points"):
        json_to_wpl(str(input_file), str(output_file), frame=3, segments=5)
