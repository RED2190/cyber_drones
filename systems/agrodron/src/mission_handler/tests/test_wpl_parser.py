"""Тесты парсера WPL."""
from systems.agrodron.src.mission_handler.src.wpl_parser import parse_wpl


# Минимальный валидный WPL: заголовок + одна точка
WPL_MINIMAL = """QGC WPL 110
0	1	0	16	0	0	0	0	60.0	30.0	5.0	1"""

# WPL с HOME (index -1) и двумя точками
WPL_WITH_HOME = """QGC WPL 110
-1	0	0	16	0	0	0	0	60.0	30.0	0.0	1
0	1	0	16	0	0	0	0	60.1	30.1	5.0	1
1	0	0	16	0	0	0	0	60.2	30.2	5.0	1"""


def test_parse_minimal_wpl():
    mission, err = parse_wpl(WPL_MINIMAL)
    assert err is None
    assert mission is not None
    assert mission["mission_id"]  # автогенерированный
    assert len(mission["steps"]) == 1
    assert mission["steps"][0]["lat"] == 60.0
    assert mission["steps"][0]["lon"] == 30.0
    assert mission["steps"][0]["alt_m"] == 5.0


def test_parse_with_mission_id():
    mission, err = parse_wpl(WPL_MINIMAL, mission_id="custom-id")
    assert err is None
    assert mission["mission_id"] == "custom-id"


def test_parse_with_home():
    mission, err = parse_wpl(WPL_WITH_HOME)
    assert err is None
    assert mission["home"]["lat"] == 60.0
    assert mission["home"]["lon"] == 30.0
    assert mission["home"]["alt_m"] == 0.0
    assert len(mission["steps"]) == 2


def test_parse_empty_fails():
    mission, err = parse_wpl("")
    assert mission is None
    assert err == "empty_or_invalid_wpl"


def test_parse_invalid_header_fails():
    mission, err = parse_wpl("NOT WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60\t30\t5\t1")
    assert mission is None
    assert "invalid" in (err or "").lower() or "empty" in (err or "").lower()
