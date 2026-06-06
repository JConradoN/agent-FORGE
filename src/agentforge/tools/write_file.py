from __future__ import annotations

import os
from pathlib import Path


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def write_file(path: str, content: str) -> str:
    """Writes content to path relative to AGENT_WORKDIR."""
    if not path or not path.strip():
        return "[ERROR] 'path' is required."
    target = (_workdir() / path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"File written: {path} ({len(content)} chars)"


def read_file(path: str) -> str:
    """Reads file at path relative to AGENT_WORKDIR. 8000 chars limit."""
    READ_MAX = 8000
    if not path or not path.strip():
        return "[ERROR] 'path' is required."
    target = (_workdir() / path).resolve()
    if not target.exists():
        return f"[ERROR] File not found: {path}"
    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > READ_MAX:
        content = content[:READ_MAX] + f"\n... [truncated — {len(content)} chars total]"
    return content


def append_file(path: str, content: str) -> str:
    """Appends content to the end of path relative to AGENT_WORKDIR."""
    if not path or not path.strip():
        return "[ERROR] 'path' is required."
    target = (_workdir() / path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(content)
    return f"Content added to: {path} ({len(content)} chars)"
