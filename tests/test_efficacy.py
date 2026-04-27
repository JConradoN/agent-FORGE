"""
Efficacy harness — structural tests that validate pipeline behaviour without
requiring a live LLM.  Uses the mock provider for deterministic execution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

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
    WorkflowSpec,
)
from agentforge.core.validation import save_agent_spec
from agentforge.generators.agent_files import build_runtime_config, build_tools_config
from agentforge.runtime.engine import AgentRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent_dir(
    tmp_path: Path,
    *,
    multi_turn: bool = False,
    memory_enabled: bool = False,
    memory_type: str = "none",
    system_prompt: str | None = None,
) -> Path:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="eff_agent", name="Efficacy Agent", purpose="Testing efficacy"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=[],
        memory=MemorySpec(type=memory_type, enabled=memory_enabled),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="mock"),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b"),
        workflow=WorkflowSpec(mode="respond_or_tool", multi_turn=multi_turn),
    )
    agent_dir = tmp_path / "eff_agent"
    agent_dir.mkdir(exist_ok=True)

    save_agent_spec(agent_dir / "agent.yaml", spec)

    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)

    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)

    if system_prompt is not None:
        (agent_dir / "system_prompt.md").write_text(system_prompt, encoding="utf-8")

    return agent_dir


# ---------------------------------------------------------------------------
# Multi-turn: histórico acumula
# ---------------------------------------------------------------------------

class TestMultiTurnConsistency:
    def test_history_empty_before_first_run(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        assert runtime.history == []

    def test_history_grows_after_each_run(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        runtime.run("mensagem 1")
        assert len(runtime.history) == 2  # user + assistant
        runtime.run("mensagem 2")
        assert len(runtime.history) == 4

    def test_history_contains_user_and_assistant_roles(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        runtime.run("pergunta")
        roles = [turn["role"] for turn in runtime.history]
        assert roles == ["user", "assistant"]

    def test_history_preserves_user_message(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        runtime.run("olá mundo")
        assert runtime.history[0]["content"] == "olá mundo"

    def test_second_turn_output_mentions_turn_number(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        runtime.run("primeiro")
        result = runtime.run("segundo")
        assert "[turn 2]" in result["output"]

    def test_first_turn_output_has_no_turn_annotation(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        result = runtime.run("primeiro")
        assert "[turn" not in result["output"]

    def test_conversation_turn_in_metadata(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        r1 = runtime.run("turno 1")
        r2 = runtime.run("turno 2")
        assert r1["metadata"]["conversation_turn"] == 1
        assert r2["metadata"]["conversation_turn"] == 2

    def test_single_turn_history_does_not_accumulate(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=False))
        runtime.run("a")
        runtime.run("b")
        assert runtime.history == []

    def test_single_turn_output_has_no_turn_annotation(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=False))
        result = runtime.run("x")
        assert "[turn" not in result["output"]

    def test_clear_history_resets_turns(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        runtime.run("a")
        runtime.run("b")
        runtime.clear_history()
        assert runtime.history == []

    def test_after_clear_next_run_is_turn_one(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
        runtime.run("a")
        runtime.clear_history()
        result = runtime.run("b")
        assert "[turn" not in result["output"]


# ---------------------------------------------------------------------------
# Contexto passado ao provider
# ---------------------------------------------------------------------------

class TestHistoryPassedToProvider:
    def test_first_call_passes_empty_history(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock, patch
        from agentforge.providers.mock import MockProvider

        captured: list = []
        original_generate = MockProvider.generate

        def _capturing_generate(self, request):
            captured.append(request.history)
            return original_generate(self, request)

        with patch.object(MockProvider, "generate", _capturing_generate):
            runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
            runtime.run("hello")

        assert captured[0] == []

    def test_second_call_passes_prior_turns(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from agentforge.providers.mock import MockProvider

        captured: list = []
        original_generate = MockProvider.generate

        def _capturing_generate(self, request):
            captured.append(request.history)
            return original_generate(self, request)

        with patch.object(MockProvider, "generate", _capturing_generate):
            runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=True))
            runtime.run("first")
            runtime.run("second")

        assert len(captured[1]) == 2
        assert captured[1][0]["role"] == "user"
        assert captured[1][0]["content"] == "first"

    def test_single_turn_always_passes_empty_history(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from agentforge.providers.mock import MockProvider

        captured: list = []
        original_generate = MockProvider.generate

        def _capturing_generate(self, request):
            captured.append(request.history)
            return original_generate(self, request)

        with patch.object(MockProvider, "generate", _capturing_generate):
            runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, multi_turn=False))
            runtime.run("a")
            runtime.run("b")

        assert all(h == [] for h in captured)


# ---------------------------------------------------------------------------
# Memória persistida entre sessões
# ---------------------------------------------------------------------------

class TestMemoryPersistence:
    def test_history_file_not_created_when_memory_disabled(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path, multi_turn=True, memory_enabled=False)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        runtime.run("x")
        assert not (agent_dir / "history.json").exists()

    def test_history_file_created_when_memory_enabled(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, multi_turn=True, memory_enabled=True, memory_type="session_summary"
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        runtime.run("x")
        assert (agent_dir / "history.json").exists()

    def test_history_file_contains_correct_turns(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, multi_turn=True, memory_enabled=True, memory_type="session_summary"
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        runtime.run("pergunta persistida")
        data = json.loads((agent_dir / "history.json").read_text())
        assert data[0] == {"role": "user", "content": "pergunta persistida"}

    def test_new_runtime_loads_persisted_history(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, multi_turn=True, memory_enabled=True, memory_type="session_summary"
        )
        rt1 = AgentRuntime.from_agent_dir(agent_dir)
        rt1.run("turno 1")

        rt2 = AgentRuntime.from_agent_dir(agent_dir)
        assert len(rt2.history) == 2
        assert rt2.history[0]["content"] == "turno 1"

    def test_new_runtime_continues_from_turn_two(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, multi_turn=True, memory_enabled=True, memory_type="session_summary"
        )
        rt1 = AgentRuntime.from_agent_dir(agent_dir)
        rt1.run("turno 1")

        rt2 = AgentRuntime.from_agent_dir(agent_dir)
        result = rt2.run("turno 2")
        assert "[turn 2]" in result["output"]

    def test_clear_history_removes_file(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, multi_turn=True, memory_enabled=True, memory_type="session_summary"
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        runtime.run("x")
        runtime.clear_history()
        assert not (agent_dir / "history.json").exists()


# ---------------------------------------------------------------------------
# Formato e aderência ao output
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_result_has_required_keys(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("x")
        for key in ("agent_id", "provider", "input", "output", "metadata", "provider_response"):
            assert key in result, f"missing key: {key}"

    def test_output_is_string(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("x")
        assert isinstance(result["output"], str)

    def test_input_preserved_verbatim(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("entrada exata")
        assert result["input"] == "entrada exata"

    def test_metadata_timestamp_is_iso(self, tmp_path: Path) -> None:
        from datetime import datetime
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("x")
        ts = result["metadata"]["timestamp"]
        datetime.fromisoformat(ts)  # raises if invalid

    def test_output_contains_input_text(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path))
        result = runtime.run("palavra-chave-especial")
        assert "palavra-chave-especial" in result["output"]

    def test_system_prompt_does_not_leak_into_output_key(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path, system_prompt="Você é um assistente secreto.")
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run("x")
        # top-level "output" should be the model response, not the prompt
        assert "secreto" not in result["output"]
