from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from browser_navigate import browser_navigate


def _mock_run(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_returns_stdout_on_success():
    with patch("browser_navigate.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="[Título: Ex]\n[URL: https://ex.com]\n\nhello")
        result = browser_navigate("https://ex.com")
    assert result == "[Título: Ex]\n[URL: https://ex.com]\n\nhello"


def test_passes_url_and_wait_selector_into_generated_script():
    with patch("browser_navigate.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="ok")
        browser_navigate("https://ex.com", wait_selector="#app")
    script_arg = mock_run.call_args.args[0][2]
    assert "https://ex.com" in script_arg
    assert "#app" in script_arg


def test_returns_error_string_on_nonzero_returncode():
    with patch("browser_navigate.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(returncode=1, stderr="playwright crashed")
        result = browser_navigate("https://ex.com")
    assert result.startswith("[ERRO browser]")
    assert "playwright crashed" in result


def test_returns_error_string_on_timeout_without_raising():
    with patch("browser_navigate.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python3", timeout=25)
        result = browser_navigate("https://ex.com")
    assert result.startswith("[ERRO browser]")
    assert "timeout" in result


def test_returns_placeholder_on_empty_stdout():
    with patch("browser_navigate.subprocess.run") as mock_run:
        mock_run.return_value = _mock_run(stdout="   ")
        result = browser_navigate("https://ex.com")
    assert result == "[sem conteúdo]"
