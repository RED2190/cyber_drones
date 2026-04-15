from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from demo.interactive_demo import DockerInteractiveDemo


ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = ROOT / "demo"
GCS_DIAGRAMS_DIR = ROOT / "systems" / "gcs" / "docs" / "diagrams"
GCS_C4_DIR = ROOT / "systems" / "gcs" / "docs" / "c4"

demo = DockerInteractiveDemo(client_id="web_demo")


@dataclass
class JobState:
    job_id: str
    action: str
    label: str
    status: str = "running"
    log_text: str = ""
    result: Any = None
    result_text: str = ""
    error: str = ""
    traceback: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None


JOB_LOCK = threading.Lock()
JOBS: Dict[str, JobState] = {}
STREAMING_ACTIONS: Dict[str, Callable[[Callable[[str], None]], Any]] = {
    "prepare": demo.prepare_systems_stream,
    "broker-up": demo.broker_up_stream,
    "gcs-up": demo.gcs_up_stream,
    "gcs-interactive-up": demo.gcs_interactive_up_stream,
    "drone-port-up": demo.drone_port_up_stream,
    "cyber-drons-up": demo.cyber_drons_up_stream,
}
