from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock


class TestMcpToolsRegistered:
    def test_collect_system_health_tool_exists(self) -> None:
        from agentforge.channels.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "collect_system_health" in tools

    def test_read_log_tail_tool_exists(self) -> None:
        from agentforge.channels.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "read_log_tail" in tools

    def test_scan_directory_tool_exists(self) -> None:
        from agentforge.channels.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "scan_directory" in tools

    def test_run_agent_tool_exists(self) -> None:
        from agentforge.channels.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "run_agent" in tools


class TestCollectSystemHealthTool:
    def test_returns_json_string(self) -> None:
        from agentforge.channels.mcp_server import collect_system_health
        result = collect_system_health()
        data = json.loads(result)
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data

    def test_returns_hostname(self) -> None:
        from agentforge.channels.mcp_server import collect_system_health
        data = json.loads(collect_system_health())
        assert "hostname" in data


class TestReadLogTailTool:
    def test_returns_json_string_with_mock(self) -> None:
        from agentforge.channels.mcp_server import read_log_tail
        mock_result = {"lines": ["linha 1", "linha 2"], "log_path": "/var/log/syslog"}
        with patch("agentforge.tools.read_log_tail.read_log_tail", return_value=mock_result):
            result = read_log_tail(log_path="/var/log/syslog", lines=10)
        data = json.loads(result)
        assert "lines" in data

    def test_default_log_path_is_syslog(self) -> None:
        from agentforge.channels.mcp_server import read_log_tail
        import inspect
        sig = inspect.signature(read_log_tail)
        assert sig.parameters["log_path"].default == "/var/log/syslog"


class TestRunAgentTool:
    def test_returns_output_string(self, tmp_path) -> None:
        from agentforge.channels.mcp_server import run_agent
        mock_runtime = MagicMock()
        mock_runtime.run.return_value = {"output": "Servidor saudável."}

        with patch("agentforge.runtime.engine.AgentRuntime.from_agent_dir", return_value=mock_runtime):
            result = run_agent("como está o servidor?", agent_dir=str(tmp_path))

        assert result == "Servidor saudável."

    def test_provider_error_returns_error_string(self, tmp_path) -> None:
        from agentforge.channels.mcp_server import run_agent
        from agentforge.providers.base import ProviderError

        with patch("agentforge.runtime.engine.AgentRuntime.from_agent_dir",
                   side_effect=ProviderError("conexão recusada")):
            result = run_agent("teste", agent_dir=str(tmp_path))

        assert "erro de provider" in result

    def test_missing_agent_returns_error_string(self, tmp_path) -> None:
        from agentforge.channels.mcp_server import run_agent

        result = run_agent("teste", agent_dir=str(tmp_path / "nao_existe"))
        assert "não encontrado" in result
