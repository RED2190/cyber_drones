"""
BaseFabricComponent — базовый класс для компонентов, работающих с Fabric через HTTP-прокси.

Каждый компонент-организация наследует этот класс и регистрирует
свои action-хендлеры. Вызовы к Fabric идут через fabric-proxy (HTTP).
"""
import os
import json
from typing import Dict, Any, List, Optional

import requests

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus


class BaseFabricComponent(BaseComponent):

    def __init__(
        self,
        component_id: str,
        component_type: str,
        topic: str,
        bus: SystemBus,
        fabric_proxy_url: Optional[str] = None,
    ):
        self.fabric_proxy_url = (
            fabric_proxy_url
            or os.environ.get("FABRIC_PROXY_URL", "http://localhost:3000")
        )
        self._channel = os.environ.get("FABRIC_CHANNEL", "dronechannel")
        self._chaincode = os.environ.get("FABRIC_CHAINCODE", "drone-chaincode")
        super().__init__(
            component_id=component_id,
            component_type=component_type,
            topic=topic,
            bus=bus,
        )
        print(f"[{component_id}] Fabric proxy: {self.fabric_proxy_url}")

    def _call_fabric(
        self,
        method: str,
        args: List[str],
        action: str = "invoke",
    ) -> Dict[str, Any]:
        """HTTP call to fabric-proxy (/api/invoke or /api/query)."""
        url = f"{self.fabric_proxy_url}/api/{action}"
        payload = {
            "channel": self._channel,
            "chaincode": self._chaincode,
            "method": method,
            "args": args,
        }
        resp = requests.post(url, json=payload, timeout=60)
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            raise RuntimeError(data.get("error", f"HTTP {resp.status_code}"))
        result_raw = data.get("result", "")
        if result_raw:
            try:
                return json.loads(result_raw)
            except (json.JSONDecodeError, TypeError):
                return {"raw": result_raw}
        return {"transaction_id": data.get("transaction_id", ""), "ok": True}
