from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from agentforge.cli.main import app
from agentforge.core.agent_models import (
    AgentIdentity,
    AgentPersona,
    AgentSpec,
    ChannelSpec,
    DeploymentSpec,
    EvaluationSpec,
    GuardrailSpec,
    MemorySpec,
    ModelPolicySpec,
    OutputSpec,
    ToolSpec,
    WorkflowSpec,
)
from agentforge.core.validation import save_agent_spec
from agentforge.generators.agent_files import build_runtime_config, build_tools_config
from agentforge.runtime.engine import AgentRuntime, RuntimeConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec() -> AgentSpec:
    return AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="test_agent", name="Test Agent", purpose="Testing"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=[ToolSpec(name="web_search")],
        memory=MemorySpec(type="session_summary", enabled=True),
        output=OutputSpec(mode="text", format="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="mock"),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b", fallback_model="qwen3:5b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )


def _make_agent_dir(tmp_path: Path) -> Path:
    spec = _make_spec()
    agent_dir = tmp_path / "test_agent"
    agent_dir.mkdir()

    save_agent_spec(agent_dir / "agent.yaml", spec)

    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)

    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)

    return agent_dir


# ---------------------------------------------------------------------------
# RuntimeConfig
# ---------------------------------------------------------------------------

class TestRuntimeConfig:
    def test_flattens_nested_yaml(self) -> None:
        data = {
            "runtime_version": "0.1",
            "agent_id": "claudio",
            "provider": "ollama",
            "model": {"default": "gemma4:e4b", "fallback": None},
            "workflow": {"mode": "respond_or_tool"},
            "channel": {"type": "telegram"},
            "memory": {"enabled": True, "type": "session_summary"},
            "output": {"mode": "text", "format": "text"},
        }
        cfg = RuntimeConfig.model_validate(data)
        assert cfg.agent_id == "claudio"
        assert cfg.provider == "ollama"
        assert cfg.model_default == "gemma4:e4b"
        assert cfg.model_fallback is None
        assert cfg.workflow_mode == "respond_or_tool"
        assert cfg.channel_type == "telegram"
        assert cfg.memory_enabled is True
        assert cfg.memory_type == "session_summary"

    def test_conversation_multi_turn_defaults_to_false(self) -> None:
        data = {
            "runtime_version": "0.1",
            "agent_id": "test",
            "provider": "mock",
            "model": {"default": "gemma4:e4b"},
            "workflow": {"mode": "respond_or_tool"},
            "channel": {"type": "cli"},
            "memory": {"enabled": False, "type": "none"},
            "output": {"mode": "text"},
        }
        cfg = RuntimeConfig.model_validate(data)
        assert cfg.conversation_multi_turn is False

    def test_conversation_multi_turn_can_be_set_true(self) -> None:
        data = {
            "runtime_version": "0.1",
            "agent_id": "test",
            "provider": "mock",
            "model": {"default": "gemma4:e4b"},
            "workflow": {"mode": "respond_or_tool"},
            "channel": {"type": "cli"},
            "memory": {"enabled": False, "type": "none"},
            "output": {"mode": "text"},
            "conversation": {"multi_turn": True},
        }
        cfg = RuntimeConfig.model_validate(data)
        assert cfg.conversation_multi_turn is True


# ---------------------------------------------------------------------------
# AgentRuntime.from_agent_dir
# ---------------------------------------------------------------------------

class TestFromAgentDir:
    def test_loads_agent_spec_id(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.agent_spec.agent.id == "test_agent"

    def test_loads_runtime_config_provider(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.runtime_config.provider == "mock"

    def test_loads_runtime_config_model(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.runtime_config.model_default == "gemma4:e4b"

    def test_loads_tools(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert len(runtime.tools) == 1
        assert runtime.tools[0].name == "web_search"

    def test_works_without_tools_yaml(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        (agent_dir / "tools.yaml").unlink()
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.tools == []

    def test_root_dir_stored(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.root_dir == agent_dir

    def test_raises_on_missing_agent_yaml(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            AgentRuntime.from_agent_dir(tmp_path / "nonexistent")


# ---------------------------------------------------------------------------
# AgentRuntime.run
# ---------------------------------------------------------------------------

class TestRun:
    def test_returns_agent_id(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert result["agent_id"] == "test_agent"

    def test_returns_input_unchanged(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert result["input"] == "teste"

    def test_output_uses_mock_provider(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert "MOCK_PROVIDER_RESPONSE" in result["output"]
        assert "teste" in result["output"]

    def test_metadata_contains_workflow_mode(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert "workflow_mode" in result["metadata"]

    def test_metadata_contains_model_default(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert "model_default" in result["metadata"]

    def test_metadata_contains_timestamp(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert "timestamp" in result["metadata"]

    def test_metadata_contains_provider(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert "provider" in result["metadata"]
        assert result["metadata"]["provider"] == "mock"

    def test_result_has_provider_response(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert "provider_response" in result
        assert result["provider_response"]["provider"] == "mock"

    def test_result_top_level_provider(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        assert result["provider"] == "mock"

    def test_extra_metadata_passed_through(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste", metadata={"source": "unit-test"})
        assert result["metadata"]["source"] == "unit-test"

    def test_context_filtered_when_single_turn(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("teste")
        raw_resp = result["provider_response"]["raw_response"]
        assert "context" not in raw_resp


# ---------------------------------------------------------------------------
# CLI — run command
# ---------------------------------------------------------------------------

class TestCliRun:
    def test_exit_code_zero(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi"])
        assert result.exit_code == 0, result.output

    def test_output_uses_mock_provider(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi"])
        assert "MOCK_PROVIDER_RESPONSE" in result.output

    def test_output_contains_agent_id(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi"])
        assert "test_agent" in result.output

    def test_missing_agent_dir_exits_nonzero(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["run", "--agent-dir", str(tmp_path / "nonexistent"), "--input", "Oi"],
        )
        assert result.exit_code != 0

    def test_mode_raw_returns_json(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi", "--mode", "raw"]
        )
        assert result.exit_code == 0
        assert '"agent_id"' in result.output

    def test_mode_pretty_returns_readable_output(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi", "--mode", "pretty"]
        )
        assert result.exit_code == 0
        assert "MOCK_PROVIDER_RESPONSE" in result.output

    def test_mode_invalid_exits_nonzero(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["run", "--agent-dir", str(agent_dir), "--input", "Oi", "--mode", "invalid"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Provider alternativo (mock)
# ---------------------------------------------------------------------------

def _make_agent_dir_with_provider(tmp_path: Path, provider: str) -> Path:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="mock_agent", name="Mock Agent", purpose="Testing"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=[],
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider=provider),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )
    agent_dir = tmp_path / "mock_agent"
    agent_dir.mkdir()

    save_agent_spec(agent_dir / "agent.yaml", spec)

    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)

    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)

    return agent_dir


# ---------------------------------------------------------------------------
# Provider ollama — testes com HTTP monkeypatched
# ---------------------------------------------------------------------------

def _mock_ollama_resp(status: int = 200) -> object:
    from unittest.mock import Mock

    r = Mock()
    r.status_code = status
    r.json.return_value = {
        "model": "gemma4:e4b",
        "response": "Resposta do Ollama.",
        "done": True,
        "context": [],
        "total_duration": 1000,
    }
    r.text = "ok"
    return r


class TestOllamaProvider:
    def test_run_with_mocked_http_succeeds(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_ollama_resp()))
        agent_dir = _make_agent_dir_with_provider(tmp_path, "ollama")
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")
        assert result["provider"] == "ollama"
        assert "Resposta do Ollama." in result["output"]

    def test_run_connection_error_raises_provider_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import requests
        from unittest.mock import Mock
        from agentforge.providers.ollama import OllamaConnectionError

        monkeypatch.setattr(
            requests, "post", Mock(side_effect=requests.exceptions.ConnectionError("refused"))
        )
        agent_dir = _make_agent_dir_with_provider(tmp_path, "ollama")
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        with pytest.raises(OllamaConnectionError):
            runtime.run("teste")

    def test_cli_run_ollama_mocked_exits_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_ollama_resp()))
        agent_dir = _make_agent_dir_with_provider(tmp_path, "ollama")
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi"])
        assert result.exit_code == 0, result.output

    def test_cli_run_ollama_connection_error_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(
            requests, "post", Mock(side_effect=requests.exceptions.ConnectionError("refused"))
        )
        agent_dir = _make_agent_dir_with_provider(tmp_path, "ollama")
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi"])
        assert result.exit_code != 0
        assert "ollama" in result.output.lower()


class TestAlternativeProvider:
    def test_loads_mock_provider(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_provider(tmp_path, "mock")
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.runtime_config.provider == "mock"

    def test_run_exposes_mock_provider_in_metadata(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_provider(tmp_path, "mock")
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")
        assert result["metadata"]["provider"] == "mock"

    def test_loads_litellm_provider(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_provider(tmp_path, "litellm")
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.runtime_config.provider == "litellm"

    def test_cli_run_shows_mock_provider(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_provider(tmp_path, "mock")
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--agent-dir", str(agent_dir), "--input", "Oi"])
        assert result.exit_code == 0, result.output
        assert "mock" in result.output
