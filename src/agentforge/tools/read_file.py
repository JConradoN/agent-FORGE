from __future__ import annotations

import os
from pathlib import Path


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def read_file(path: str) -> str:
    """Reads a file from path relative to AGENT_WORKDIR (or absolute)."""
    if not path or not path.strip():
        return "[ERROR] 'path' is required."
    p = Path(path)
    if not p.is_absolute():
        p = (_workdir() / path).resolve()
    if not p.exists():
        return f"[ERROR] File not found: {p}"
    return p.read_text(encoding="utf-8")
