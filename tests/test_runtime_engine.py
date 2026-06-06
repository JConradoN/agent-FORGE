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
        assert raw_resp is None or "context" not in raw_resp


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


# ---------------------------------------------------------------------------
# Tool calling pipeline
# ---------------------------------------------------------------------------

def _make_agent_dir_with_tools(tmp_path: Path, tools: list[ToolSpec]) -> Path:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="tool_agent", name="Tool Agent", purpose="Testing tools"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=tools,
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="ollama"),
        model_policy=ModelPolicySpec(default_model="qwen3.5:9b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )
    agent_dir = tmp_path / "tool_agent"
    agent_dir.mkdir()
    save_agent_spec(agent_dir / "agent.yaml", spec)
    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)
    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)
    return agent_dir


def _mock_chat_tool_call_resp(tool_name: str, args: dict | None = None) -> object:
    from unittest.mock import Mock
    r = Mock()
    r.status_code = 200
    r.json.return_value = {
        "model": "qwen3.5:9b",
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": tool_name, "arguments": args or {}}}
            ],
        },
        "done": True,
    }
    r.text = "ok"
    return r


def _mock_simple_resp(text: str = "Resposta.") -> object:
    """Mock para /api/generate (sem history, sem tools)."""
    from unittest.mock import Mock
    r = Mock()
    r.status_code = 200
    r.json.return_value = {"model": "qwen3.5:9b", "response": text, "done": True}
    r.text = "ok"
    return r


def _mock_chat_text_resp(text: str = "Resposta final.") -> object:
    from unittest.mock import Mock
    r = Mock()
    r.status_code = 200
    r.json.return_value = {
        "model": "qwen3.5:9b",
        "message": {"role": "assistant", "content": text},
        "done": True,
    }
    r.text = "ok"
    return r


class TestBuildToolsSchema:
    def test_empty_tools_returns_empty_list(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_tools(tmp_path, [])
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        schema = runtime._build_tools_schema()
        assert schema == []

    def test_tool_appears_in_schema(self, tmp_path: Path) -> None:
        tools = [ToolSpec(name="collect_system_health", description="Coleta métricas")]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        schema = runtime._build_tools_schema()
        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "collect_system_health"

    def test_when_to_use_included_in_description(self, tmp_path: Path) -> None:
        tools = [ToolSpec(
            name="collect_system_health",
            description="Coleta métricas",
            when_to_use="quando perguntado sobre saúde do servidor",
            when_not_to_use="para perguntas sobre código",
        )]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        schema = runtime._build_tools_schema()
        desc = schema[0]["function"]["description"]
        assert "quando perguntado sobre saúde do servidor" in desc
        assert "para perguntas sobre código" in desc

    def test_multiple_tools_all_appear(self, tmp_path: Path) -> None:
        tools = [
            ToolSpec(name="collect_system_health", description="Saúde"),
            ToolSpec(name="read_log_tail", description="Logs"),
        ]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        schema = runtime._build_tools_schema()
        names = [s["function"]["name"] for s in schema]
        assert "collect_system_health" in names
        assert "read_log_tail" in names


class TestToolCallingCycle:
    def test_model_calls_tool_and_gets_second_inference(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock, call

        responses = [
            _mock_chat_tool_call_resp("collect_system_health"),
            _mock_chat_text_resp("CPU está em 10%."),
        ]
        mock_post = Mock(side_effect=responses)
        monkeypatch.setattr(requests, "post", mock_post)

        tools = [ToolSpec(name="collect_system_health", description="Coleta métricas")]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("Como está o servidor?")

        assert result["output"] == "CPU está em 10%."
        assert mock_post.call_count == 2

    def test_tool_calls_logged_in_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            _mock_chat_tool_call_resp("collect_system_health"),
            _mock_chat_text_resp("OK."),
        ]))

        tools = [ToolSpec(name="collect_system_health", description="Coleta")]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("estado?")

        log = result["metadata"]["tool_calls_log"]
        assert log is not None
        assert log[0]["tool"] == "collect_system_health"

    def test_no_tool_call_returns_direct_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_chat_text_resp("Resposta direta.")))

        tools = [ToolSpec(name="collect_system_health", description="Coleta")]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("olá")

        assert result["output"] == "Resposta direta."
        assert result["metadata"]["tool_calls_log"] is None

    def test_tools_schema_passed_to_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        mock_post = Mock(return_value=_mock_chat_text_resp("ok"))
        monkeypatch.setattr(requests, "post", mock_post)

        tools = [ToolSpec(name="collect_system_health", description="Coleta")]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        runtime.run("teste")

        posted = mock_post.call_args[1]["json"]
        assert "tools" in posted
        assert posted["tools"][0]["function"]["name"] == "collect_system_health"


# ---------------------------------------------------------------------------
# agentforge eval command
# ---------------------------------------------------------------------------

class TestEvalCommand:
    def test_eval_creates_jsonl_output(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_provider(tmp_path, "mock")
        dataset = tmp_path / "dataset.yaml"
        dataset.write_text(
            "cases:\n  - input: 'Olá'\n    notes: 'teste básico'\n",
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(app, [
            "eval",
            "--agent-dir", str(agent_dir),
            "--dataset", str(dataset),
        ])
        assert result.exit_code == 0, result.output
        eval_dir = agent_dir / "eval_runs"
        assert eval_dir.exists()
        jsonl_files = list(eval_dir.glob("*.jsonl"))
        assert len(jsonl_files) == 1

    def test_eval_records_input_and_output(self, tmp_path: Path) -> None:
        import json as _json
        agent_dir = _make_agent_dir_with_provider(tmp_path, "mock")
        dataset = tmp_path / "dataset.yaml"
        dataset.write_text(
            "cases:\n  - input: 'Qual é o estado?'\n",
            encoding="utf-8",
        )
        runner = CliRunner()
        runner.invoke(app, ["eval", "--agent-dir", str(agent_dir), "--dataset", str(dataset)])
        jsonl = next((agent_dir / "eval_runs").glob("*.jsonl"))
        entry = _json.loads(jsonl.read_text())
        assert entry["input"] == "Qual é o estado?"
        assert entry["ok"] is True
        assert "output" in entry

    def test_eval_missing_dataset_exits_nonzero(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_provider(tmp_path, "mock")
        runner = CliRunner()
        result = runner.invoke(app, [
            "eval",
            "--agent-dir", str(agent_dir),
            "--dataset", str(tmp_path / "ghost.yaml"),
        ])
        assert result.exit_code != 0

    def test_eval_reports_case_count(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir_with_provider(tmp_path, "mock")
        dataset = tmp_path / "dataset.yaml"
        dataset.write_text(
            "cases:\n  - input: 'A'\n  - input: 'B'\n  - input: 'C'\n",
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(app, ["eval", "--agent-dir", str(agent_dir), "--dataset", str(dataset)])
        assert "3/3" in result.output


# ---------------------------------------------------------------------------
# Loop guard
# ---------------------------------------------------------------------------

class TestLoopGuard:
    def test_repeated_tool_call_stops_loop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        # ciclo 0: pede tool; ciclo 1: pede mesma tool → loop detectado; final: resposta
        tool_resp = _mock_chat_tool_call_resp("collect_system_health")
        final_resp = _mock_chat_text_resp("Detectei loop, respondo direto.")
        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            tool_resp, tool_resp, final_resp,
        ]))

        tools = [ToolSpec(name="collect_system_health", description="Coleta")]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("estado?")

        # Deve retornar sem explodir — loop guard acionado
        assert result["output"] is not None
        assert len(result["output"]) > 0

    def test_max_tool_cycles_respected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        # 2 tools diferentes → 2 ciclos → final
        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            _mock_chat_tool_call_resp("collect_system_health"),
            _mock_chat_tool_call_resp("read_log_tail"),
            _mock_chat_text_resp("Resposta após 2 ciclos."),
        ]))

        tools = [
            ToolSpec(name="collect_system_health", description="Saúde"),
            ToolSpec(name="read_log_tail", description="Logs"),
        ]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("estado e logs?")
        assert result["output"] == "Resposta após 2 ciclos."

    def test_tool_calls_log_includes_cycle_number(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            _mock_chat_tool_call_resp("collect_system_health"),
            _mock_chat_text_resp("OK."),
        ]))

        tools = [ToolSpec(name="collect_system_health", description="Coleta")]
        agent_dir = _make_agent_dir_with_tools(tmp_path, tools)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("estado?")

        log = result["metadata"]["tool_calls_log"]
        assert log[0]["cycle"] == 0


# ---------------------------------------------------------------------------
# Reflexão autônoma
# ---------------------------------------------------------------------------

def _make_agent_dir_with_reflection(tmp_path: Path, reflection_rounds: int) -> Path:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="reflect_agent", name="Reflect Agent", purpose="Testing"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=[],
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="ollama"),
        model_policy=ModelPolicySpec(default_model="qwen3.5:9b"),
        workflow=WorkflowSpec(mode="respond_or_tool", reflection_rounds=reflection_rounds),
    )
    agent_dir = tmp_path / "reflect_agent"
    agent_dir.mkdir()
    save_agent_spec(agent_dir / "agent.yaml", spec)
    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)
    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)
    return agent_dir


class TestReflection:
    def test_zero_reflection_rounds_single_inference(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        # sem tools → _generate_simple → formato "response"
        mock_post = Mock(return_value=_mock_simple_resp("Primeira resposta."))
        monkeypatch.setattr(requests, "post", mock_post)

        agent_dir = _make_agent_dir_with_reflection(tmp_path, reflection_rounds=0)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")

        assert result["output"] == "Primeira resposta."
        assert mock_post.call_count == 1

    def test_one_reflection_round_calls_provider_twice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        # call 1: inferência principal (simple); call 2: reflexão (simple)
        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            _mock_simple_resp("Primeira resposta."),
            _mock_simple_resp("Resposta refinada."),
        ]))

        agent_dir = _make_agent_dir_with_reflection(tmp_path, reflection_rounds=1)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")

        assert result["output"] == "Resposta refinada."

    def test_two_reflection_rounds_calls_provider_three_times(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import requests
        from unittest.mock import Mock

        mock_post = Mock(side_effect=[
            _mock_simple_resp("v1"),
            _mock_simple_resp("v2"),
            _mock_simple_resp("v3"),
        ])
        monkeypatch.setattr(requests, "post", mock_post)

        agent_dir = _make_agent_dir_with_reflection(tmp_path, reflection_rounds=2)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")

        assert result["output"] == "v3"
        assert mock_post.call_count == 3


# ---------------------------------------------------------------------------
# Guardrails ativos
# ---------------------------------------------------------------------------

def _make_agent_dir_with_guardrails(tmp_path: Path, must_not: list[str]) -> Path:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="guard_agent", name="Guard Agent", purpose="Testing"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=[],
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(must_not=must_not),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="ollama"),
        model_policy=ModelPolicySpec(default_model="qwen3.5:9b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )
    agent_dir = tmp_path / "guard_agent"
    agent_dir.mkdir()
    save_agent_spec(agent_dir / "agent.yaml", spec)
    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)
    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)
    return agent_dir


class TestGuardrails:
    def test_no_must_not_rules_skips_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem must_not, nenhuma chamada extra ao provider."""
        import requests
        from unittest.mock import Mock

        mock_post = Mock(return_value=_mock_simple_resp("Resposta normal."))
        monkeypatch.setattr(requests, "post", mock_post)

        agent_dir = _make_agent_dir_with_guardrails(tmp_path, must_not=[])
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")

        assert result["output"] == "Resposta normal."
        assert mock_post.call_count == 1
        assert result["metadata"].get("guardrail_violations") is None

    def test_clean_output_passes_without_retry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Output sem violação: 1 chamada principal + 1 check (NENHUMA)."""
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            _mock_simple_resp("Resposta legítima."),   # inferência principal
            _mock_simple_resp("NENHUMA"),               # check guardrail
        ]))

        agent_dir = _make_agent_dir_with_guardrails(tmp_path, must_not=["inventar dados"])
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")

        assert result["output"] == "Resposta legítima."
        assert result["metadata"].get("guardrail_violations") is None

    def test_violation_triggers_retry_and_corrects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Violação detectada → retry → output corrigido, sem violações residuais."""
        import requests
        from unittest.mock import Mock

        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            _mock_simple_resp("Inventei dados falsos."),    # inferência principal
            _mock_simple_resp("inventar dados"),            # check → violação
            _mock_simple_resp("Dados reais do sistema."),  # correção (retry)
            _mock_simple_resp("NENHUMA"),                   # re-check → limpo
        ]))

        agent_dir = _make_agent_dir_with_guardrails(tmp_path, must_not=["inventar dados"])
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")

        assert result["output"] == "Dados reais do sistema."
        assert result["metadata"].get("guardrail_violations") is None

    def test_persistent_violation_recorded_in_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Violação persiste após todos os retries → registrada em guardrail_violations."""
        import requests
        from unittest.mock import Mock

        # 1 main + 1 check + 2*(1 retry + 1 check) = 6 chamadas totais
        monkeypatch.setattr(requests, "post", Mock(side_effect=[
            _mock_simple_resp("Ainda inventei dados."),    # inferência principal
            _mock_simple_resp("inventar dados"),           # check inicial → violação
            _mock_simple_resp("Continuo inventando."),     # retry 0
            _mock_simple_resp("inventar dados"),           # re-check → ainda violação
            _mock_simple_resp("Invento mais uma vez."),    # retry 1
            _mock_simple_resp("inventar dados"),           # re-check → persistente
        ]))

        agent_dir = _make_agent_dir_with_guardrails(tmp_path, must_not=["inventar dados"])
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("teste")

        violations = result["metadata"].get("guardrail_violations")
        assert violations is not None
        assert len(violations) > 0
