from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from browser_get_element import browser_get_element


def _mock_run(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_returns_stdout_on_success():
    with patch("browser_get_element.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="Example Domain")
        result = browser_get_element("https://ex.com", "h1")
    assert result == "Example Domain"


def test_passes_url_and_selector_into_generated_script():
    with patch("browser_get_element.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="ok")
        browser_get_element("https://ex.com", "#price")
    script_arg = mock_run.call_args.args[0][2]
    assert "https://ex.com" in script_arg
    assert "#price" in script_arg


def test_returns_error_string_on_nonzero_returncode():
    with patch("browser_get_element.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(returncode=1, stderr="boom")
        result = browser_get_element("https://ex.com", "h1")
    assert result.startswith("[ERRO browser]")


def test_returns_error_string_on_timeout_without_raising():
    with patch("browser_get_element.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python3", timeout=25)
        result = browser_get_element("https://ex.com", "h1")
    assert result.startswith("[ERRO browser]")
