"""Unit тесты для системы Operator (моки, без брокера)."""
from unittest.mock import MagicMock

from systems.operator.src.gateway.src.gateway import OperatorGateway
from systems.operator.src.gateway.topics import ComponentTopics, GatewayActions, SystemTopics
from systems.operator.src.operator_component.src.operator_component import OperatorComponent
from systems.operator.src.operator_component.topics import OperatorActions


def test_register_drone():
    bus = MagicMock()
    comp = OperatorComponent(component_id="operator_component", bus=bus)
    msg = {
        "action": OperatorActions.REGISTER_DRONE,
        "payload": {"drone_id": "d1", "model": "Agrodron", "capabilities": {"type": "agrodron"}},
    }
    result = comp._handlers[OperatorActions.REGISTER_DRONE](msg)
    assert result["status"] == "registered"
    assert result["drone_id"] == "d1"
    assert "d1" in comp._drones


def test_request_available_drones_empty():
    bus = MagicMock()
    comp = OperatorComponent(component_id="operator_component", bus=bus)
    msg = {"action": OperatorActions.REQUEST_AVAILABLE_DRONES, "payload": {"budget": 1000}}
    result = comp._handlers[OperatorActions.REQUEST_AVAILABLE_DRONES](msg)
    assert result["drones"] == []


def test_request_available_drones_with_registered():
    bus = MagicMock()
    comp = OperatorComponent(component_id="operator_component", bus=bus)

    comp._drones["d1"] = {"drone_id": "d1", "model": "X", "status": "available", "operator_id": "op"}
    comp._drones["d2"] = {"drone_id": "d2", "model": "Y", "status": "assigned", "operator_id": "op"}

    msg = {"action": OperatorActions.REQUEST_AVAILABLE_DRONES, "payload": {"budget": 500}}
    result = comp._handlers[OperatorActions.REQUEST_AVAILABLE_DRONES](msg)
    assert len(result["drones"]) == 1
    assert result["drones"][0]["drone_id"] == "d1"


def test_buy_insurance_calls_insurer():
    bus = MagicMock()
    bus.request.return_value = {
        "success": True,
        "payload": {"policy_id": "pol1", "status": "active"},
    }
    comp = OperatorComponent(component_id="operator_component", bus=bus)
    msg = {
        "action": OperatorActions.BUY_INSURANCE_POLICY,
        "payload": {"drone_id": "d1", "coverage_amount": 5000, "order_id": "o1"},
    }
    result = comp._handlers[OperatorActions.BUY_INSURANCE_POLICY](msg)
    assert result["status"] == "insured"
    assert result["policy"]["policy_id"] == "pol1"
    bus.request.assert_called_once()


def test_report_incident_calls_insurer_with_incident_payload():
    bus = MagicMock()
    bus.request.return_value = {
        "success": True,
        "payload": {"payment_amount": 1200, "coverage_amount": 1200},
    }
    comp = OperatorComponent(component_id="operator_component", bus=bus)
    msg = {
        "action": OperatorActions.BUY_INSURANCE_POLICY,
        "payload": {
            "drone_id": "d1",
            "coverage_amount": 1200,
            "order_id": "o1",
            "insurance_action": "report_incident",
            "incident": {"damage_amount": 1200, "incident_type": "motor_failure"},
        },
    }
    result = comp._handlers[OperatorActions.BUY_INSURANCE_POLICY](msg)
    assert result["status"] == "incident_processed"
    assert result["claim"]["payment_amount"] == 1200

    bus.request.assert_called_once()
    _, request_message = bus.request.call_args[0]
    assert request_message["action"] == "report_incident"
    assert request_message["payload"]["incident"]["damage_amount"] == 1200


def test_register_in_orvd_calls_orvd():
    bus = MagicMock()
    bus.request.return_value = {
        "success": True,
        "payload": {"status": "registered", "drone_id": "d1"},
    }
    comp = OperatorComponent(component_id="operator_component", bus=bus)
    msg = {
        "action": OperatorActions.REGISTER_DRONE_IN_ORVD,
        "payload": {"drone_id": "d1", "model": "Agrodron"},
    }
    result = comp._handlers[OperatorActions.REGISTER_DRONE_IN_ORVD](msg)
    assert result["status"] == "registered_in_orvd"
    bus.request.assert_called_once()


def test_operator_gateway_routes_actions():
    bus = MagicMock()
    gw = OperatorGateway(system_id="operator", bus=bus, health_port=None)
    assert gw.topic == SystemTopics.OPERATOR
    assert gw.ACTION_ROUTING[GatewayActions.REGISTER_DRONE] == ComponentTopics.OPERATOR_COMPONENT
    assert gw.ACTION_ROUTING[GatewayActions.REQUEST_AVAILABLE_DRONES] == ComponentTopics.OPERATOR_COMPONENT
    assert gw.ACTION_ROUTING[GatewayActions.BUY_INSURANCE_POLICY] == ComponentTopics.OPERATOR_COMPONENT


def test_send_order_to_nus():
    bus = MagicMock()
    comp = OperatorComponent(component_id="operator_component", bus=bus)
    msg = {
        "action": OperatorActions.SEND_ORDER_TO_NUS,
        "payload": {"order_id": "O-1"},
    }
    result = comp._handlers[OperatorActions.SEND_ORDER_TO_NUS](msg)
    assert result["status"] == "sent_to_nus"
