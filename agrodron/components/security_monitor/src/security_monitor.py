"""
SecurityMonitorComponent - компонент-монитор безопасности.
"""
import json
import os
from typing import Dict, Any, Tuple, Set, Optional

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus
from components.security_monitor import config


PolicyKey = Tuple[str, str, str]


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
        # Разворачиваем шаблоны: "${SYSTEM_NAME}", "$SYSTEM_NAME", "$${SYSTEM_NAME}" -> system_name().
        if isinstance(raw_policies, str) and raw_policies:
            sys_name = config.system_name()
            raw_policies = (
                raw_policies.replace("$${SYSTEM_NAME}", sys_name)
                .replace("${SYSTEM_NAME}", sys_name)
                .replace("$SYSTEM_NAME", sys_name)
            )
        self._policies: Set[PolicyKey] = self._parse_policies(raw_policies)
        self._mode: str = "NORMAL"  # NORMAL | ISOLATED

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
        self.register_handler("ISOLATION_START", self._handle_isolation_start)
        self.register_handler("isolation_status", self._handle_isolation_status)

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
        except Exception:
            pass

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
        return (sender_id, target_topic, target_action) in self._policies

    # ------------------------------------------------------- isolation support

    def _load_emergency_policies(self) -> None:
        """
        Заменяет текущие политики на фиксированный аварийный набор.
        """
        emergency: Set[PolicyKey] = {
            ("emergensy", config.topic_for("navigation"), "GET_LAST_STATE"),
            ("emergensy", config.topic_for("motors"), "LAND"),
            ("emergensy", config.topic_for("sprayer"), "SET_SPRAY"),
            ("emergensy", config.topic_for("journal"), "LOG_EVENT"),
            ("emergensy", config.topic_for("security_monitor"), "isolation_status"),
        }
        self._policies = emergency
        self._mode = "ISOLATED"

    def _handle_isolation_start(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Обработчик команды ISOLATION_START.

        Предполагается, что инициатором выступает компонент emergensy.
        """
        sender = str(message.get("sender", "")).strip()
        # Разрешаем только emergensy или администратора политик.
        if not (sender.startswith("emergensy") or self._can_manage_policies(sender)):
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
            "action": "LOG_EVENT",
            "sender": self.component_id,
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
            return None

        target_topic, target_action, target_payload = target
        if not self._is_allowed(sender_id, target_topic, target_action):
            return None

        request_message = {
            "action": target_action,
            "sender": self.component_id,
            "payload": target_payload,
        }
        response = self.bus.request(
            target_topic,
            request_message,
            timeout=config.proxy_request_timeout_s(),
        )
        if not response:
            return None

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

        publish_message = {
            "action": target_action,
            "sender": self.component_id,
            "payload": target_payload,
        }
        published = self.bus.publish(target_topic, publish_message)
        return {"published": bool(published)}
