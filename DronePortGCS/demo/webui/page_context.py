from __future__ import annotations

import subprocess
from typing import Any

from demo.webui.runtime import GCS_C4_DIR, GCS_DIAGRAMS_DIR, ROOT
from demo.webui.security import parse_security_analysis


def _read_git_file(ref: str, path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return ""


def build_index_context() -> dict[str, Any]:
    diagrams = []
    if GCS_DIAGRAMS_DIR.exists():
        for path in sorted(GCS_DIAGRAMS_DIR.iterdir()):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}:
                continue
            diagrams.append(
                {
                    "name": path.name,
                    "title": path.stem.replace("_", " "),
                    "url": f"/gcs-diagrams/{path.name}",
                }
            )

    security_artifacts = []
    if GCS_C4_DIR.exists():
        for filename in ("C2_Containers_Trust.puml", "C1_Context.puml", "C2_Containers.puml", "README.md"):
            path = GCS_C4_DIR / filename
            if path.exists():
                security_artifacts.append(
                    {
                        "name": path.name,
                        "title": path.stem.replace("_", " "),
                        "url": f"/gcs-c4/{path.name}",
                    }
                )

    remote_security_analysis = _read_git_file("origin/security-analysis", "docs/GCS_SECURITY_ANALYSIS.md")
    return {
        "diagrams": diagrams,
        "security_artifacts": security_artifacts,
        "security_analysis": parse_security_analysis(remote_security_analysis),
    }
