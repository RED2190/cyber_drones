"""Тесты протокола сообщений SDK."""
import pytest
from sdk.messages import Message, create_response


def test_message_create():
    msg = Message(action="echo", payload={"data": "test"}, sender="sender_1")
    assert msg.action == "echo"
    assert msg.payload == {"data": "test"}
    assert msg.sender == "sender_1"


def test_message_to_dict():
    msg = Message(action="ping", sender="s1")
    d = msg.to_dict()
    assert d["action"] == "ping"
    assert d["sender"] == "s1"
    assert "timestamp" in d
    assert "correlation_id" not in d


def test_message_to_dict_with_correlation():
    msg = Message(action="ping", sender="s1", correlation_id="abc")
    d = msg.to_dict()
    assert d["correlation_id"] == "abc"


def test_message_from_dict():
    data = {"action": "echo", "payload": {"x": 1}, "sender": "test"}
    msg = Message.from_dict(data)
    assert msg.action == "echo"
    assert msg.payload == {"x": 1}
    assert msg.sender == "test"


def test_message_from_dict_defaults():
    msg = Message.from_dict({})
    assert msg.action == ""
    assert msg.payload == {}
    assert msg.sender == ""


def test_create_response_success():
    resp = create_response(
        correlation_id="123",
        payload={"result": 42},
        sender="sys_1"
    )
    assert resp["action"] == "response"
    assert resp["correlation_id"] == "123"
    assert resp["payload"] == {"result": 42}
    assert resp["sender"] == "sys_1"
    assert resp["success"] is True
    assert "error" not in resp
    assert "timestamp" in resp


def test_create_response_error():
    resp = create_response(
        correlation_id="456",
        payload={},
        sender="sys_1",
        success=False,
        error="something failed"
    )
    assert resp["success"] is False
    assert resp["error"] == "something failed"
