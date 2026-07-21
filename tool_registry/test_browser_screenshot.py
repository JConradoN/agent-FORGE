from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from browser_screenshot import browser_screenshot


def _mock_run(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_returns_stdout_on_success():
    with patch("browser_screenshot.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="Screenshot salvo: /tmp/page.png")
        result = browser_screenshot("https://ex.com", "page.png")
    assert result == "Screenshot salvo: /tmp/page.png"


def test_resolves_filename_against_agent_workdir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WORKDIR", str(tmp_path))
    with patch("browser_screenshot.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="ok")
        browser_screenshot("https://ex.com", "page.png")
    script_arg = mock_run.call_args.args[0][2]
    assert str(tmp_path / "page.png") in script_arg


def test_returns_error_string_on_nonzero_returncode():
    with patch("browser_screenshot.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(returncode=1, stderr="boom")
        result = browser_screenshot("https://ex.com", "page.png")
    assert result.startswith("[ERRO browser]")


def test_returns_error_string_on_timeout_without_raising():
    with patch("browser_screenshot.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python3", timeout=25)
        result = browser_screenshot("https://ex.com", "page.png")
    assert result.startswith("[ERRO browser]")
