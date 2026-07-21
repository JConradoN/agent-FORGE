from __future__ import annotations

import time

import pytest

from agentforge.tools.run_bash import run_bash


@pytest.fixture(autouse=True)
def _workdir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WORKDIR", str(tmp_path))
    return tmp_path


def test_requires_command():
    assert "required" in run_bash("").lower()
    assert "required" in run_bash("   ").lower()


def test_runs_command_and_captures_output():
    out = run_bash("echo hello")
    assert "hello" in out


def test_blocks_destructive_rm():
    out = run_bash("rm -rf /")
    assert "BLOCKED" in out


def test_reports_nonzero_exit_output():
    out = run_bash("echo failing >&2; exit 1")
    assert "failing" in out


def test_backgrounded_server_does_not_hang_the_call(monkeypatch):
    """Regression test for 2026-07-21: a command that backgrounds a
    longer-lived process without fully redirecting its own stdout/stderr
    used to hang the whole call for the entire BASH_TIMEOUT window, because
    subprocess.run's pipe (capture_output=True) never saw EOF — the
    backgrounded grandchild kept the write end open indefinitely, even
    though the actual command (starting the server) had already succeeded
    and the shell that launched it had long since exited.
    """
    monkeypatch.setenv("BASH_TIMEOUT", "1800")
    start = time.monotonic()
    out = run_bash("(sleep 30 &) ; echo launched")
    elapsed = time.monotonic() - start

    assert "launched" in out
    # Must return once the shell itself exits, not wait out the backgrounded
    # sleep (30s) or anywhere near the 1800s BASH_TIMEOUT.
    assert elapsed < 10


def test_timeout_still_applies_to_a_genuinely_slow_foreground_command(monkeypatch):
    monkeypatch.setenv("BASH_TIMEOUT", "1")
    out = run_bash("sleep 5")
    assert "Timeout after 1s" in out
