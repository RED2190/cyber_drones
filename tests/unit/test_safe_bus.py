"""Тесты для SafeBus и BaseSecurityMonitor."""
import pytest
from unittest.mock import MagicMock

from sdk.safe_bus import SafeBus, SECURITY_MONITOR_TOPIC, DEAD_LETTER_TOPIC
from sdk.security_monitor import BaseSecurityMonitor


def _make_bus(**kwargs):
    inner = MagicMock()
    bus = SafeBus(inner, **kwargs)
    return bus, inner


class TestPublishApproved:
    def test_delivers_when_approved(self):
        bus, inner = _make_bus()
        inner.request.return_value = {
            "success": True,
            "payload": {"approved": True, "reason": ""},
        }
        inner.publish.return_value = True

        result = bus.publish("systems.test", {"action": "echo", "sender": "x"})

        assert result is True
        inner.request.assert_called_once()
        inner.publish.assert_called_once_with(
            "systems.test", {"action": "echo", "sender": "x"},
        )


class TestPublishDenied:
    def test_blocks_and_sends_dead_letter(self):
        bus, inner = _make_bus()
        inner.request.return_value = {
            "success": True,
            "payload": {"approved": False, "reason": "forbidden"},
        }

        result = bus.publish("systems.test", {"action": "echo", "sender": "x"})

        assert result is False
        topic, msg = inner.publish.call_args[0]
        assert topic == DEAD_LETTER_TOPIC
        assert msg["action"] == "security_blocked"
        assert msg["error"] == "forbidden"


class TestMonitorUnavailable:
    def test_publish_blocked_on_timeout(self):
        bus, inner = _make_bus()
        inner.request.return_value = None

        result = bus.publish("systems.test", {"action": "echo", "sender": "x"})

        assert result is False

    def test_request_returns_none_on_timeout(self):
        bus, inner = _make_bus()
        inner.request.return_value = None

        result = bus.request("systems.test", {"action": "get", "sender": "x"})

        assert result is None


class TestRequestWithMonitor:
    def test_approved(self):
        bus, inner = _make_bus()
        inner.request.side_effect = [
            {"success": True, "payload": {"approved": True, "reason": ""}},
            {"success": True, "payload": {"data": 42}},
        ]

        result = bus.request("systems.test", {"action": "get", "sender": "x"})

        assert result == {"success": True, "payload": {"data": 42}}
        assert inner.request.call_count == 2

    def test_denied(self):
        bus, inner = _make_bus()
        inner.request.return_value = {
            "success": True,
            "payload": {"approved": False, "reason": "no"},
        }

        result = bus.request("systems.test", {"action": "get", "sender": "x"})

        assert result is None


class TestSkipRules:
    def test_response_bypasses(self):
        bus, inner = _make_bus()
        inner.publish.return_value = True

        bus.publish("reply.topic", {"action": "response", "correlation_id": "1"})

        inner.request.assert_not_called()

    def test_dead_letter_bypasses(self):
        bus, inner = _make_bus()
        inner.publish.return_value = True

        bus.publish(DEAD_LETTER_TOPIC, {"action": "dead_letter"})

        inner.request.assert_not_called()

    def test_monitor_topic_bypasses(self):
        bus, inner = _make_bus()
        inner.publish.return_value = True

        bus.publish(SECURITY_MONITOR_TOPIC, {"action": "test"})

        inner.request.assert_not_called()


class TestDelegation:
    def setup_method(self):
        self.bus, self.inner = _make_bus()

    def test_subscribe(self):
        cb = lambda msg: None
        self.bus.subscribe("topic", cb)
        self.inner.subscribe.assert_called_once_with("topic", cb)

    def test_unsubscribe(self):
        self.bus.unsubscribe("topic")
        self.inner.unsubscribe.assert_called_once_with("topic")

    def test_start(self):
        self.bus.start()
        self.inner.start.assert_called_once()

    def test_stop(self):
        self.bus.stop()
        self.inner.stop.assert_called_once()

    def test_request_async(self):
        self.bus.request_async("topic", {"action": "x"}, timeout=5.0)
        self.inner.request_async.assert_called_once()


class TestRespondBypassesMonitor:
    def test_respond_no_check(self):
        bus, inner = _make_bus()
        inner.publish.return_value = True

        bus.respond({"reply_to": "r", "correlation_id": "abc"}, {"data": 1})

        inner.request.assert_not_called()
        topic, _ = inner.publish.call_args[0]
        assert topic == "r"


class TestBaseSecurityMonitor:
    def test_default_approves(self):
        monitor = BaseSecurityMonitor(bus=MagicMock())
        result = monitor._handle_security_check({
            "action": "security_check",
            "payload": {"target_topic": "t", "action": "echo",
                        "sender": "s", "payload": {}},
        })
        assert result["approved"] is True

    def test_custom_policy(self):
        class Strict(BaseSecurityMonitor):
            def check_message(self, target_topic, action, sender, payload):
                if action == "bad":
                    return False, "denied"
                return True, ""

        monitor = Strict(bus=MagicMock())

        assert monitor._handle_security_check({
            "action": "security_check",
            "payload": {"target_topic": "t", "action": "bad",
                        "sender": "x", "payload": {}},
        })["approved"] is False

        assert monitor._handle_security_check({
            "action": "security_check",
            "payload": {"target_topic": "t", "action": "ok",
                        "sender": "x", "payload": {}},
        })["approved"] is True

    def test_has_handlers(self):
        monitor = BaseSecurityMonitor(bus=MagicMock())
        assert "security_check" in monitor._handlers
        assert "ping" in monitor._handlers
