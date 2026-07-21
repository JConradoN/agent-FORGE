from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from browser_execute_js import browser_execute_js


def _mock_run(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_returns_stdout_on_success():
    with patch("browser_execute_js.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="document title here")
        result = browser_execute_js("https://ex.com", "document.title")
    assert result == "document title here"


def test_passes_url_and_script_into_generated_script():
    with patch("browser_execute_js.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="ok")
        browser_execute_js("https://ex.com", "document.querySelectorAll('a').length")
    script_arg = mock_run.call_args.args[0][2]
    assert "https://ex.com" in script_arg
    assert "querySelectorAll" in script_arg


def test_returns_error_string_on_nonzero_returncode():
    with patch("browser_execute_js.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(returncode=1, stderr="boom")
        result = browser_execute_js("https://ex.com", "1+1")
    assert result.startswith("[ERRO browser]")


def test_returns_error_string_on_timeout_without_raising():
    with patch("browser_execute_js.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python3", timeout=25)
        result = browser_execute_js("https://ex.com", "1+1")
    assert result.startswith("[ERRO browser]")
