from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

_DEFAULT_BASH_TIMEOUT = 1800

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
    """Executes command in AGENT_WORKDIR with a BASH_TIMEOUT-second timeout (default 1800s). Destructive commands are blocked."""
    if not command or not command.strip():
        return "[ERROR] 'command' is required."

    bash_timeout = int(os.environ.get("BASH_TIMEOUT", str(_DEFAULT_BASH_TIMEOUT)))

    block = _is_blocked(command)
    if block:
        return block

    workdir = _workdir()
    workdir.mkdir(parents=True, exist_ok=True)

    # stdout/stderr go to a real file, not a pipe. subprocess.run's
    # capture_output=True (a pipe) hangs indefinitely — well past the
    # timeout=BASH_TIMEOUT below — whenever the command backgrounds a
    # longer-lived child (`python3 -m http.server {port} &`) without fully
    # redirecting its own fds: the pipe's write end stays open in that
    # grandchild even after the shell itself exits, so communicate() never
    # sees EOF. Confirmed 2026-07-21: a model correctly started the required
    # server, but the tool call itself sat blocked for the full 30-minute
    # BASH_TIMEOUT before erroring — even though the server had already come
    # up successfully. A regular file has no such blocking-reader semantics:
    # once the shell we actually launched exits, Popen.wait() returns
    # immediately regardless of what any backgrounded descendant is still
    # doing, and we just read however much output had been written by then.
    with tempfile.TemporaryFile() as out_f:
        try:
            proc = subprocess.Popen(
                command,
                shell=True,  # nosec B602 — intentional: this tool executes agent-issued shell commands; blocklist above guards destructive patterns
                stdout=out_f,
                stderr=subprocess.STDOUT,
                cwd=str(workdir),
                start_new_session=True,
            )
            proc.wait(timeout=bash_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return f"[ERROR] Timeout after {bash_timeout}s."
        except Exception as e:
            return f"[ERROR] {e}"

        out_f.seek(0)
        out = out_f.read().decode("utf-8", errors="replace")
        if len(out) > 4000:
            out = out[:4000] + f"\n... [truncated — {len(out)} chars total]"
        return out or "(no output)"
