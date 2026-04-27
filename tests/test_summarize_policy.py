"""
Tests for the "summarize" history policy.
All tests are deterministic — no live LLM required.
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
from agentforge.runtime.memory import (
    _SUMMARY_PREFIX,
    _SUMMARY_ROLE,
    _build_summary_content,
    _is_summary_message,
    apply_limit_summarize,
    apply_window,
)


# ---------------------------------------------------------------------------
# Unit: _is_summary_message
# ---------------------------------------------------------------------------

class TestIsSummaryMessage:
    def test_recognizes_valid_summary(self) -> None:
        msg = {"role": _SUMMARY_ROLE, "content": f"{_SUMMARY_PREFIX}\n- Usuário: x"}
        assert _is_summary_message(msg) is True

    def test_rejects_user_role(self) -> None:
        msg = {"role": "user", "content": f"{_SUMMARY_PREFIX}\n- Usuário: x"}
        assert _is_summary_message(msg) is False

    def test_rejects_assistant_role(self) -> None:
        msg = {"role": "assistant", "content": f"{_SUMMARY_PREFIX}\n- x"}
        assert _is_summary_message(msg) is False

    def test_rejects_system_without_prefix(self) -> None:
        msg = {"role": "system", "content": "Você é um assistente."}
        assert _is_summary_message(msg) is False

    def test_rejects_empty_content(self) -> None:
        msg = {"role": "system", "content": ""}
        assert _is_summary_message(msg) is False


# ---------------------------------------------------------------------------
# Unit: _build_summary_content
# ---------------------------------------------------------------------------

class TestBuildSummaryContent:
    def test_starts_with_prefix(self) -> None:
        content = _build_summary_content(None, [{"role": "user", "content": "oi"}])
        assert content.startswith(_SUMMARY_PREFIX)

    def test_user_turn_labeled_usuario(self) -> None:
        content = _build_summary_content(None, [{"role": "user", "content": "pergunta"}])
        assert "- Usuário: pergunta" in content

    def test_assistant_turn_labeled_assistente(self) -> None:
        content = _build_summary_content(None, [{"role": "assistant", "content": "resposta"}])
        assert "- Assistente: resposta" in content

    def test_preserves_existing_content(self) -> None:
        existing = f"{_SUMMARY_PREFIX}\n- Usuário: antigo"
        content = _build_summary_content(existing, [{"role": "user", "content": "novo"}])
        assert "- Usuário: antigo" in content
        assert "- Usuário: novo" in content

    def test_newlines_in_content_replaced(self) -> None:
        content = _build_summary_content(None, [{"role": "user", "content": "linha1\nlinha2"}])
        assert "\n- " not in content.split(_SUMMARY_PREFIX, 1)[1].split("\n- Usuário:")[0]
        assert "linha1 linha2" in content


# ---------------------------------------------------------------------------
# Unit: apply_limit_summarize
# ---------------------------------------------------------------------------

class TestApplyLimitSummarize:
    def _turns(self, n: int) -> list[dict[str, str]]:
        result = []
        for i in range(n):
            result.append({"role": "user", "content": f"u{i}"})
            result.append({"role": "assistant", "content": f"a{i}"})
        return result

    def test_zero_means_unlimited(self) -> None:
        h = self._turns(10)
        assert apply_limit_summarize(h, 0) is h

    def test_empty_unchanged(self) -> None:
        assert apply_limit_summarize([], 3) == []

    def test_within_limit_unchanged(self) -> None:
        h = self._turns(2)
        assert apply_limit_summarize(h, 5) == h

    def test_exactly_at_limit_unchanged(self) -> None:
        h = self._turns(3)
        assert apply_limit_summarize(h, 3) == h

    def test_overflow_creates_summary_as_first_entry(self) -> None:
        h = self._turns(4)
        result = apply_limit_summarize(h, 2)
        assert result[0]["role"] == _SUMMARY_ROLE
        assert result[0]["content"].startswith(_SUMMARY_PREFIX)

    def test_overflow_keeps_last_n_verbatim(self) -> None:
        h = self._turns(4)  # u0,a0,u1,a1,u2,a2,u3,a3
        result = apply_limit_summarize(h, 2)
        # last 2 turns: u2,a2,u3,a3
        verbatim = result[1:]
        assert verbatim[0]["content"] == "u2"
        assert verbatim[1]["content"] == "a2"
        assert verbatim[2]["content"] == "u3"
        assert verbatim[3]["content"] == "a3"

    def test_summary_contains_overflow_bullets(self) -> None:
        h = self._turns(3)  # max_turns=1 → overflow=[u0,a0,u1,a1], keep=[u2,a2]
        result = apply_limit_summarize(h, 1)
        summary_text = result[0]["content"]
        assert "u0" in summary_text
        assert "a0" in summary_text
        assert "u1" in summary_text

    def test_second_overflow_updates_existing_summary(self) -> None:
        h = self._turns(4)
        after_first = apply_limit_summarize(h, 2)
        # Simulate adding 2 more turns
        after_first = after_first + self._turns(2)[2:]  # append u1,a1 equivalent
        after_first.append({"role": "user", "content": "u4"})
        after_first.append({"role": "assistant", "content": "a4"})
        result = apply_limit_summarize(after_first, 2)
        # Still exactly one system summary
        system_msgs = [m for m in result if m["role"] == _SUMMARY_ROLE]
        assert len(system_msgs) == 1

    def test_second_overflow_accumulates_in_single_summary(self) -> None:
        h = self._turns(3)
        r1 = apply_limit_summarize(h, 2)
        # r1 = [summary(u0), u1,a1, u2,a2]
        r1.append({"role": "user", "content": "u3"})
        r1.append({"role": "assistant", "content": "a3"})
        r2 = apply_limit_summarize(r1, 2)
        # r2 summary should contain u0 AND u1
        summary_text = r2[0]["content"]
        assert "u0" in summary_text
        assert "u1" in summary_text

    def test_result_has_max_turns_plus_one_for_summary(self) -> None:
        h = self._turns(5)
        result = apply_limit_summarize(h, 2)
        # 1 summary + 2*2 verbatim messages = 5
        assert len(result) == 5

    def test_custom_summarizer_called(self) -> None:
        called_with: list = []

        def my_summarizer(overflow, existing):
            called_with.append((overflow, existing))
            return f"{_SUMMARY_PREFIX}\n- custom"

        h = self._turns(3)
        apply_limit_summarize(h, 2, summarizer=my_summarizer)
        assert len(called_with) == 1
        overflow_arg, existing_arg = called_with[0]
        assert overflow_arg[0]["content"] == "u0"
        assert existing_arg is None

    def test_custom_summarizer_output_used(self) -> None:
        def my_summarizer(overflow, existing):
            return f"{_SUMMARY_PREFIX}\n- INJECTED"

        h = self._turns(3)
        result = apply_limit_summarize(h, 2, summarizer=my_summarizer)
        assert "INJECTED" in result[0]["content"]


# ---------------------------------------------------------------------------
# Unit: apply_window routing
# ---------------------------------------------------------------------------

class TestApplyWindow:
    def test_summarize_policy_uses_summarize_path(self) -> None:
        h = [
            {"role": "user", "content": "u0"}, {"role": "assistant", "content": "a0"},
            {"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"}, {"role": "assistant", "content": "a2"},
        ]
        result = apply_window(h, 2, policy="summarize")
        assert result[0]["role"] == _SUMMARY_ROLE

    def test_truncate_policy_uses_truncate_path(self) -> None:
        h = [
            {"role": "user", "content": "u0"}, {"role": "assistant", "content": "a0"},
            {"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"}, {"role": "assistant", "content": "a2"},
        ]
        result = apply_window(h, 2, policy="truncate")
        assert result[0]["role"] == "user"  # no system summary

    def test_unknown_policy_falls_back_to_truncate(self) -> None:
        h = [
            {"role": "user", "content": "u0"}, {"role": "assistant", "content": "a0"},
            {"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"}, {"role": "assistant", "content": "a2"},
        ]
        result = apply_window(h, 2, policy="unknown_policy")
        assert result[0]["role"] == "user"


# ---------------------------------------------------------------------------
# Helper: runtime factory
# ---------------------------------------------------------------------------

def _make_agent_dir(
    tmp_path: Path,
    *,
    multi_turn: bool = True,
    memory_enabled: bool = False,
    memory_type: str = "none",
    max_turns: int = 0,
    policy: str = "truncate",
) -> Path:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="sum_agent", name="Sum Agent", purpose="Testing summarize"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=[],
        memory=MemorySpec(
            type=memory_type,
            enabled=memory_enabled,
            max_turns=max_turns,
            policy=policy,
        ),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="mock"),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b"),
        workflow=WorkflowSpec(mode="respond_or_tool", multi_turn=multi_turn),
    )
    agent_dir = tmp_path / "sum_agent"
    agent_dir.mkdir(exist_ok=True)
    save_agent_spec(agent_dir / "agent.yaml", spec)
    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)
    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)
    return agent_dir


def _run_n(runtime: AgentRuntime, n: int) -> None:
    for i in range(n):
        runtime.run(f"msg {i}")


# ---------------------------------------------------------------------------
# Integration: summarize in runtime
# ---------------------------------------------------------------------------

class TestSummarizeInRuntime:
    def test_below_limit_no_summary_message(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=3, policy="summarize")
        )
        _run_n(runtime, 2)
        assert not any(m["role"] == _SUMMARY_ROLE for m in runtime.history)

    def test_overflow_creates_summary_message(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="summarize")
        )
        _run_n(runtime, 3)
        assert runtime.history[0]["role"] == _SUMMARY_ROLE

    def test_summary_content_contains_overflow_text(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="summarize")
        )
        runtime.run("mensagem zero")
        runtime.run("mensagem um")
        runtime.run("mensagem dois")  # triggers overflow: msg zero → summary
        summary_text = runtime.history[0]["content"]
        assert "msg 0" in summary_text or "mensagem zero" in summary_text

    def test_overflow_keeps_last_n_turns_verbatim(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="summarize")
        )
        _run_n(runtime, 4)
        # history: [summary, u2,a2, u3,a3]
        verbatim = runtime.history[1:]
        assert len(verbatim) == 4

    def test_second_overflow_no_duplicate_summary(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="summarize")
        )
        _run_n(runtime, 6)
        system_msgs = [m for m in runtime.history if m["role"] == _SUMMARY_ROLE]
        assert len(system_msgs) == 1

    def test_second_overflow_summary_contains_earlier_turns(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="summarize")
        )
        _run_n(runtime, 5)
        summary_text = runtime.history[0]["content"]
        # first 3 overflow turns should all be in the summary
        assert "msg 0" in summary_text
        assert "msg 1" in summary_text
        assert "msg 2" in summary_text

    def test_total_history_length_bounded(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="summarize")
        )
        _run_n(runtime, 20)
        # 1 summary + 2 turns * 2 messages = 5
        assert len(runtime.history) == 5

    def test_provider_receives_summary_in_history(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from agentforge.providers.mock import MockProvider

        captured: list = []
        original = MockProvider.generate

        def _cap(self, req):
            captured.append(list(req.history))
            return original(self, req)

        with patch.object(MockProvider, "generate", _cap):
            runtime = AgentRuntime.from_agent_dir(
                _make_agent_dir(tmp_path, max_turns=1, policy="summarize")
            )
            _run_n(runtime, 3)

        # Third call's history should start with summary
        last_history = captured[-1]
        assert last_history[0]["role"] == _SUMMARY_ROLE

    def test_single_turn_never_gets_summary(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, multi_turn=False, max_turns=1, policy="summarize")
        )
        _run_n(runtime, 10)
        assert runtime.history == []


# ---------------------------------------------------------------------------
# Integration: disk persistence with summarize
# ---------------------------------------------------------------------------

class TestSummarizePersistence:
    def test_history_file_contains_summary(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary",
            max_turns=2, policy="summarize"
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        _run_n(runtime, 3)
        data = json.loads((agent_dir / "history.json").read_text())
        assert data[0]["role"] == _SUMMARY_ROLE

    def test_history_file_summary_contains_overflow_content(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary",
            max_turns=2, policy="summarize"
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        _run_n(runtime, 3)
        data = json.loads((agent_dir / "history.json").read_text())
        assert "msg 0" in data[0]["content"]

    def test_new_session_loads_summary_message(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary",
            max_turns=2, policy="summarize"
        )
        rt1 = AgentRuntime.from_agent_dir(agent_dir)
        _run_n(rt1, 3)

        rt2 = AgentRuntime.from_agent_dir(agent_dir)
        assert rt2.history[0]["role"] == _SUMMARY_ROLE

    def test_new_session_continues_accumulating_summary(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary",
            max_turns=2, policy="summarize"
        )
        rt1 = AgentRuntime.from_agent_dir(agent_dir)
        _run_n(rt1, 3)  # overflow on turn 3, summary gets turn 0

        rt2 = AgentRuntime.from_agent_dir(agent_dir)
        _run_n(rt2, 2)  # overflow again, summary should now include turn 1 too

        system_msgs = [m for m in rt2.history if m["role"] == _SUMMARY_ROLE]
        assert len(system_msgs) == 1
        assert "msg 0" in system_msgs[0]["content"]
        assert "msg 1" in system_msgs[0]["content"]

    def test_disk_matches_in_memory_after_summarize(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary",
            max_turns=2, policy="summarize"
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        _run_n(runtime, 5)
        disk = json.loads((agent_dir / "history.json").read_text())
        assert disk == runtime.history


# ---------------------------------------------------------------------------
# Regression: truncate unaffected
# ---------------------------------------------------------------------------

class TestTruncateRegression:
    def test_truncate_no_summary_message(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="truncate")
        )
        _run_n(runtime, 5)
        assert not any(m["role"] == _SUMMARY_ROLE for m in runtime.history)

    def test_truncate_bounded_length(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, max_turns=2, policy="truncate")
        )
        _run_n(runtime, 10)
        assert len(runtime.history) == 4  # 2 turns * 2 messages
