"""
SecurityMonitorComponent - компонент-монитор безопасности.
"""
import json
import logging
import os
import time
from typing import Dict, Any, Tuple, Set, Optional

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus
from systems.agrodron.src.topic_utils import topic_prefix

from systems.agrodron.src.security_monitor import config


PolicyKey = Tuple[str, str, str]

logger = logging.getLogger(__name__)


class SecurityMonitorComponent(BaseComponent):

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str = "",
        policy_admin_sender: Optional[str] = None,
        security_policies: Optional[str] = None,
    ):
        self._policy_admin_sender = (
            policy_admin_sender
            if policy_admin_sender is not None
            else os.environ.get("POLICY_ADMIN_SENDER", "")
        ).strip()
        raw_policies = security_policies if security_policies is not None else os.environ.get("SECURITY_POLICIES", "")
        # "${SYSTEM_NAME}" в шаблоне политик -> topic_prefix (v1.<System>.<Instance>), как в prepare_system.
        if isinstance(raw_policies, str) and raw_policies:
            tp = topic_prefix()
            raw_policies = (
                raw_policies.replace("$${SYSTEM_NAME}", tp)
                .replace("${SYSTEM_NAME}", tp)
                .replace("$SYSTEM_NAME", tp)
            )
        self._policies: Set[PolicyKey] = self._parse_policies(raw_policies)
        self._mode: str = "NORMAL"  # NORMAL | ISOLATED
        self._ready: bool = False

        # Диагностика загрузки политик (при 0 политик — проверить SECURITY_POLICIES в контейнере)
        n = len(self._policies)
        logger.info("[%s] loaded %d policies from SECURITY_POLICIES", component_id, n)
        if n == 0 and raw_policies:
            logger.warning(
                "[%s] SECURITY_POLICIES non-empty but parsed 0 policies (first 200 chars): %r",
                component_id, (raw_policies[:200] if isinstance(raw_policies, str) else raw_policies),
            )
        elif n == 0:
            logger.warning("[%s] SECURITY_POLICIES is empty", component_id)

        super().__init__(
            component_id=component_id,
            component_type="security_monitor",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler("proxy_request", self._handle_proxy_request)
        self.register_handler("proxy_publish", self._handle_proxy_publish)
        self.register_handler("set_policy", self._handle_set_policy)
        self.register_handler("remove_policy", self._handle_remove_policy)
        self.register_handler("clear_policies", self._handle_clear_policies)
        self.register_handler("list_policies", self._handle_list_policies)
        self.register_handler("isolation_start", self._handle_isolation_start)
        self.register_handler("isolation_status", self._handle_isolation_status)

    def start(self) -> None:
        super().start()
        self._ready = self._warm_up_subscription()

    def _handle_get_status(self, message: Dict[str, Any]) -> Dict[str, Any]:
        status = super()._handle_get_status(message)
        status.update(
            {
                "ready": self._ready,
                "mode": self._mode,
                "policies_count": len(self._policies),
            }
        )
        return status

    def _warm_up_subscription(self) -> bool:
        warmup_s = config.subscribe_warmup_s()
        if warmup_s <= 0:
            logger.info("[%s] subscribe warmup disabled", self.component_id)
            return True

        deadline = time.monotonic() + warmup_s
        probe_timeout_s = config.startup_probe_timeout_s()
        attempts = 0

        while True:
            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                break

            attempts += 1
            try:
                response = self.bus.request(
                    self.topic,
                    {"action": "ping", "sender": self.topic},
                    timeout=min(probe_timeout_s, remaining_s),
                )
                payload = response.get("payload") if isinstance(response, dict) else None
                if isinstance(payload, dict) and payload.get("pong") is True:
                    logger.info(
                        "[%s] subscribe warmup ready after %d probe(s)",
                        self.component_id,
                        attempts,
                    )
                    return True
            except Exception as exc:
                logger.debug("[%s] subscribe warmup probe failed: %s", self.component_id, exc)

            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                break
            time.sleep(min(0.1, remaining_s))

        logger.warning(
            "[%s] subscribe warmup did not confirm readiness after %.1fs; continuing",
            self.component_id,
            warmup_s,
        )
        return False

    def _log_component_started(self) -> None:
        """Журнал принимает log_event только от топика МБ — публикуем напрямую."""
        from systems.agrodron.src.topic_utils import topic_for

        journal_topic = topic_for("journal")
        msg = {
            "action": "log_event",
            "sender": self.topic,
            "payload": {
                "event": "SECURITY_MONITOR_STARTED",
                "source": "security_monitor",
                "details": {
                    "policies_count": len(self._policies),
                    "mode": self._mode,
                },
            },
        }
        try:
            self.bus.publish(journal_topic, msg)
        except Exception as exc:
            logger.debug("[%s] journal startup log: %s", self.component_id, exc)

    def _parse_policies(self, raw: str) -> Set[PolicyKey]:
        if not raw:
            return set()

        parsed: Set[PolicyKey] = set()
        raw = raw.strip()

        try:
            value = json.loads(raw)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        sender = str(item.get("sender", "")).strip()
                        topic = str(item.get("topic", "")).strip()
                        action = str(item.get("action", "")).strip()
                        if sender and topic and action:
                            parsed.add((sender, topic, action))
                    elif isinstance(item, (list, tuple)) and len(item) == 3:
                        sender = str(item[0]).strip()
                        topic = str(item[1]).strip()
                        action = str(item[2]).strip()
                        if sender and topic and action:
                            parsed.add((sender, topic, action))
                return parsed
        except Exception as e:
            logger.warning("SECURITY_POLICIES JSON parse failed: %s", e)

        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = [p.strip() for p in chunk.split(",")]
            if len(parts) != 3:
                continue
            sender, topic, action = parts
            if sender and topic and action:
                parsed.add((sender, topic, action))
        return parsed

    def _policy_to_dict(self, policy: PolicyKey) -> Dict[str, str]:
        sender, topic, action = policy
        return {"sender": sender, "topic": topic, "action": action}

    def _extract_policy(self, payload: Dict[str, Any]) -> Optional[PolicyKey]:
        sender = str(payload.get("sender", "")).strip()
        topic = str(payload.get("topic", "")).strip()
        action = str(payload.get("action", "")).strip()
        if not sender or not topic or not action:
            return None
        return (sender, topic, action)

    def _extract_target(self, payload: Dict[str, Any]) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        target = payload.get("target") or {}
        target_topic = str(target.get("topic", "")).strip()
        target_action = str(target.get("action", "")).strip()
        if not target_topic or not target_action:
            return None
        target_payload = payload.get("data", {}) or {}
        if not isinstance(target_payload, dict):
            target_payload = {}
        return target_topic, target_action, target_payload

    def _can_manage_policies(self, sender: str) -> bool:
        return bool(self._policy_admin_sender and sender == self._policy_admin_sender)

    def _handle_set_policy(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sender = str(message.get("sender", "")).strip()
        if not self._can_manage_policies(sender):
            return {"updated": False, "error": "forbidden"}

        payload = message.get("payload", {}) or {}
        policy = self._extract_policy(payload)
        if policy is None:
            return {"updated": False, "error": "invalid_policy"}

        self._policies.add(policy)
        return {"updated": True, "policy": self._policy_to_dict(policy)}

    def _handle_remove_policy(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sender = str(message.get("sender", "")).strip()
        if not self._can_manage_policies(sender):
            return {"removed": False, "error": "forbidden"}

        payload = message.get("payload", {}) or {}
        policy = self._extract_policy(payload)
        if policy is None:
            return {"removed": False, "error": "invalid_policy"}

        existed = policy in self._policies
        self._policies.discard(policy)
        return {"removed": existed, "policy": self._policy_to_dict(policy)}

    def _handle_clear_policies(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sender = str(message.get("sender", "")).strip()
        if not self._can_manage_policies(sender):
            return {"cleared": False, "error": "forbidden"}

        removed = len(self._policies)
        self._policies.clear()
        return {"cleared": True, "removed_count": removed}

    def _handle_list_policies(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        policies = [self._policy_to_dict(p) for p in sorted(self._policies)]
        return {
            "policy_admin_sender": self._policy_admin_sender,
            "count": len(policies),
            "policies": policies,
        }

    def _is_allowed(self, sender_id: str, target_topic: str, target_action: str) -> bool:
        key = (sender_id, target_topic, target_action)
        if key in self._policies:
            return True
        # Шаблоны "*" в topic и/или action: любой топик и/или любое действие (для system_monitor и др.).
        for s, t, a in self._policies:
            if s != sender_id:
                continue
            topic_ok = t == "*" or t == target_topic
            action_ok = a == "*" or a == target_action
            if topic_ok and action_ok:
                return True
        return False

    # ------------------------------------------------------- isolation support

    def _load_emergency_policies(self) -> None:
        """
        Заменяет текущие политики на фиксированный аварийный набор.
        """
        emergensy_topic = config.topic_for("emergensy")
        emergency: Set[PolicyKey] = {
            (emergensy_topic, config.topic_for("navigation"), "get_state"),
            (emergensy_topic, config.topic_for("motors"), "land"),
            (emergensy_topic, config.topic_for("sprayer"), "set_spray"),
            (emergensy_topic, config.topic_for("journal"), "log_event"),
            (emergensy_topic, config.topic_for("security_monitor"), "isolation_status"),
        }
        self._policies = emergency
        self._mode = "ISOLATED"

    def _handle_isolation_start(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Обработчик команды ISOLATION_START.

        Предполагается, что инициатором выступает компонент emergensy.
        """
        sender = str(message.get("sender", "")).strip()
        emergensy_topic = config.topic_for("emergensy")
        if not (sender == emergensy_topic or self._can_manage_policies(sender)):
            return {"activated": False, "error": "forbidden"}

        self._load_emergency_policies()
        self._log_isolation_activated()
        return {"activated": True, "mode": self._mode}

    def _handle_isolation_status(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return {"mode": self._mode}

    def _log_isolation_activated(self) -> None:
        """Запись события включения изоляции в журнал (прямая публикация, МБ — доверенный отправитель)."""
        journal_topic = config.topic_for("journal")
        msg = {
            "action": "log_event",
            "sender": self.topic,
            "payload": {
                "event": "SECURITY_MONITOR_ISOLATION_ACTIVATED",
                "source": "security_monitor",
                "details": {"mode": self._mode},
            },
        }
        self.bus.publish(journal_topic, msg)

    def _handle_proxy_request(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = message.get("payload", {}) or {}
        sender_id = str(message.get("sender") or "unknown")
        target = self._extract_target(payload)
        if target is None:
            logger.warning("[%s] proxy_request: no target in payload", self.component_id)
            return {"ok": False, "error": "no_target_in_payload"}

        target_topic, target_action, target_payload = target
        logger.info(
            "[%s] proxy_request: sender=%s -> %s action=%s (reply_to=%s)",
            self.component_id, sender_id, target_topic, target_action,
            "yes" if message.get("reply_to") else "no",
        )
        if not self._is_allowed(sender_id, target_topic, target_action):
            logger.warning(
                "[%s] proxy_request denied by policy: sender=%s topic=%s action=%s",
                self.component_id, sender_id, target_topic, target_action,
            )
            return {
                "ok": False,
                "error": "policy_denied",
                "sender": sender_id,
                "target_topic": target_topic,
                "target_action": target_action,
            }

        # RAW mode: target_action == "__raw__" means "send payload as-is" (SITL-style, no action/sender wrapper).
        if target_action == "__raw__":
            request_message = dict(target_payload) if isinstance(target_payload, dict) else {}
        else:
            request_message = {
                "action": target_action,
                "sender": self.topic,
                "payload": target_payload,
            }
        timeout_s = config.proxy_request_timeout_s()
        logger.info("[%s] proxy_request -> bus.request(%s, timeout=%.1fs)", self.component_id, target_topic, timeout_s)
        response = self.bus.request(
            target_topic,
            request_message,
            timeout=timeout_s,
        )
        if not response:
            logger.warning("[%s] proxy_request: no response from %s (timeout or error)", self.component_id, target_topic)
            return {
                "ok": False,
                "error": "target_timeout",
                "target_topic": target_topic,
                "target_action": target_action,
            }

        logger.info("[%s] proxy_request: got response from %s, replying to client", self.component_id, target_topic)
        return {
            "target_topic": target_topic,
            "target_action": target_action,
            "target_response": response,
        }

    def _handle_proxy_publish(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = message.get("payload", {}) or {}
        sender_id = str(message.get("sender") or "unknown")
        target = self._extract_target(payload)
        if target is None:
            return None

        target_topic, target_action, target_payload = target
        if not self._is_allowed(sender_id, target_topic, target_action):
            return None

        if target_action == "__raw__":
            publish_message = dict(target_payload) if isinstance(target_payload, dict) else {}
        else:
            publish_message = {
                "action": target_action,
                "sender": self.topic,
                "payload": target_payload,
            }
        published = self.bus.publish(target_topic, publish_message)
        return {"published": bool(published)}
