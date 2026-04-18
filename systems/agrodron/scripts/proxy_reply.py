"""
Разбор ответа bus.request после цепочки proxy_request → security_monitor → целевой компонент.

В MQTT клиент получает полное сообщение (create_response): полезная нагрузка МБ лежит в
``payload.target_response``, а не в корне ``target_response``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def unwrap_proxy_target_response(response: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Возвращает внутренний dict ответа целевого компонента (target_response)."""
    if not isinstance(response, dict):
        return None
    outer = response.get("payload")
    if isinstance(outer, dict) and "target_response" in outer:
        tr = outer.get("target_response")
        return tr if isinstance(tr, dict) else None
    tr = response.get("target_response")
    return tr if isinstance(tr, dict) else None


def extract_navigation_nav_state_from_target_response(
    target_response: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Плоский NAV_STATE из ответа navigation `get_state` после unwrap_proxy_target_response.

    Navigation возвращает create_response, где payload = {nav_state, config, payload: <снимок>}.
    Автопилот/ограничитель ожидают на верхнем уровне lat/lon/alt_m — без этой распаковки
    float(lat) падает и управление молча не выполняется.
    """
    if not isinstance(target_response, dict):
        return None
    inner = target_response.get("payload")
    if not isinstance(inner, dict):
        return None
    if "lat" in inner and "lon" in inner:
        return inner
    actual = inner.get("payload")
    if isinstance(actual, dict) and ("lat" in actual or "alt_m" in actual):
        return actual
    actual = inner.get("nav_state")
    if isinstance(actual, dict):
        return actual
    return None
