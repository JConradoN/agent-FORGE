from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

BASH_TIMEOUT = 120

_BLOCKLIST = [
    r"rm\s+-[a-z]*rf",
    r"rm\s+-[a-z]*fr",
    r":\(\)\s*\{",
    r"dd\s+if=/dev/",
    r"mkfs",
    r"fdisk",
    r">\s*/dev/sd",
    r"wget\s+.*\|\s*bash",
    r"curl\s+.*\|\s*bash",
    r"curl\s+.*\|\s*sh",
    r"chmod\s+777\s+/",
    r"sudo\s+rm",
    r"shutdown",
    r"reboot",
]


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def _is_blocked(command: str) -> str | None:
    cmd_lower = command.lower()
    for pattern in _BLOCKLIST:
        if re.search(pattern, cmd_lower):
            return f"[BLOCKED] Command not allowed (pattern: {pattern})."
    return None


def run_bash(command: str) -> str:
    """Executes command in AGENT_WORKDIR with a 120s timeout. Destructive commands are blocked."""
    if not command or not command.strip():
        return "[ERROR] 'command' is required."

    block = _is_blocked(command)
    if block:
        return block

    workdir = _workdir()
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.run(
            command,
            shell=True,  # nosec B602 — intentional: this tool executes agent-issued shell commands; blocklist above guards destructive patterns
            capture_output=True,
            text=True,
            cwd=str(workdir),
            timeout=BASH_TIMEOUT,
        )
        out = proc.stdout + proc.stderr
        if len(out) > 4000:
            out = out[:4000] + f"\n... [truncated — {len(out)} chars total]"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[ERROR] Timeout after {BASH_TIMEOUT}s."
    except Exception as e:
        return f"[ERROR] {e}"
