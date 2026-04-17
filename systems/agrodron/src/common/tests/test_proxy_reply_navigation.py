"""Тесты распаковки ответа navigation get_state."""
from systems.agrodron.src.common.proxy_reply import extract_navigation_nav_state_from_target_response


def test_extract_from_create_response_shape():
    nav = {"lat": 55.0, "lon": 37.0, "alt_m": 10.0}
    target_response = {
        "action": "response",
        "payload": {"nav_state": nav, "config": {}, "payload": nav},
        "sender": "v1.Agrodron.Agrodron001.navigation",
    }
    assert extract_navigation_nav_state_from_target_response(target_response) == nav


def test_extract_flat_payload_already_nav():
    nav = {"lat": 1.0, "lon": 2.0, "alt_m": 3.0}
    target_response = {"payload": nav}
    assert extract_navigation_nav_state_from_target_response(target_response) == nav
