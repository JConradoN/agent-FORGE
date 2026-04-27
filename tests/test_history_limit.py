"""
Tests for history windowing (max_turns limit + truncate policy).
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
from agentforge.runtime.memory import apply_limit


# ---------------------------------------------------------------------------
# Unit tests: apply_limit
# ---------------------------------------------------------------------------

class TestApplyLimit:
    def _turns(self, n: int) -> list[dict[str, str]]:
        result = []
        for i in range(n):
            result.append({"role": "user", "content": f"u{i}"})
            result.append({"role": "assistant", "content": f"a{i}"})
        return result

    def test_zero_means_unlimited(self) -> None:
        history = self._turns(100)
        assert apply_limit(history, 0) is history

    def test_negative_means_unlimited(self) -> None:
        history = self._turns(5)
        assert apply_limit(history, -1) is history

    def test_empty_history_unchanged(self) -> None:
        assert apply_limit([], 3) == []

    def test_within_limit_unchanged(self) -> None:
        history = self._turns(2)
        result = apply_limit(history, 5)
        assert result == history

    def test_exactly_at_limit_unchanged(self) -> None:
        history = self._turns(3)
        result = apply_limit(history, 3)
        assert result == history

    def test_over_limit_truncates_oldest(self) -> None:
        history = self._turns(5)  # 10 messages
        result = apply_limit(history, 2)
        assert len(result) == 4  # 2 turns = 4 messages

    def test_over_limit_keeps_most_recent(self) -> None:
        history = self._turns(5)
        result = apply_limit(history, 2)
        assert result[-1]["content"] == "a4"
        assert result[-2]["content"] == "u4"

    def test_limit_one_keeps_last_turn(self) -> None:
        history = self._turns(5)
        result = apply_limit(history, 1)
        assert len(result) == 2
        assert result[0]["content"] == "u4"
        assert result[1]["content"] == "a4"

    def test_result_is_new_list(self) -> None:
        history = self._turns(5)
        result = apply_limit(history, 2)
        assert result is not history


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_agent_dir(
    tmp_path: Path,
    *,
    multi_turn: bool = True,
    memory_enabled: bool = False,
    memory_type: str = "none",
    max_turns: int = 0,
) -> Path:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="limit_agent", name="Limit Agent", purpose="Testing limits"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        tools=[],
        memory=MemorySpec(
            type=memory_type,
            enabled=memory_enabled,
            max_turns=max_turns,
        ),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="mock"),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b"),
        workflow=WorkflowSpec(mode="respond_or_tool", multi_turn=multi_turn),
    )
    agent_dir = tmp_path / "limit_agent"
    agent_dir.mkdir(exist_ok=True)

    save_agent_spec(agent_dir / "agent.yaml", spec)

    with (agent_dir / "runtime.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True, sort_keys=False)

    with (agent_dir / "tools.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True, sort_keys=False)

    return agent_dir


def _run_n_times(runtime: AgentRuntime, n: int) -> None:
    for i in range(n):
        runtime.run(f"mensagem {i}")


# ---------------------------------------------------------------------------
# In-memory limit
# ---------------------------------------------------------------------------

class TestInMemoryLimit:
    def test_zero_limit_keeps_all_turns(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, max_turns=0))
        _run_n_times(runtime, 10)
        assert len(runtime.history) == 20  # 10 turns = 20 messages

    def test_limit_caps_history_length(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, max_turns=3))
        _run_n_times(runtime, 5)
        assert len(runtime.history) == 6  # 3 turns = 6 messages

    def test_limit_preserves_most_recent(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, max_turns=2))
        for i in range(5):
            runtime.run(f"msg {i}")
        assert runtime.history[0]["content"] == "msg 3"
        assert runtime.history[2]["content"] == "msg 4"

    def test_limit_one_keeps_only_last_turn(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, max_turns=1))
        _run_n_times(runtime, 5)
        assert len(runtime.history) == 2
        assert runtime.history[0]["role"] == "user"

    def test_no_limit_single_turn_history_empty(self, tmp_path: Path) -> None:
        runtime = AgentRuntime.from_agent_dir(
            _make_agent_dir(tmp_path, multi_turn=False, max_turns=0)
        )
        _run_n_times(runtime, 5)
        assert runtime.history == []


# ---------------------------------------------------------------------------
# Limit applied to provider input
# ---------------------------------------------------------------------------

class TestLimitPassedToProvider:
    def test_provider_receives_windowed_history(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from agentforge.providers.mock import MockProvider

        captured: list = []
        original = MockProvider.generate

        def _capture(self, request):
            captured.append(list(request.history))
            return original(self, request)

        with patch.object(MockProvider, "generate", _capture):
            runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, max_turns=2))
            _run_n_times(runtime, 5)

        # Last call should have received only 2 turns (4 messages) in history
        assert len(captured[-1]) == 4

    def test_provider_receives_most_recent_turns(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from agentforge.providers.mock import MockProvider

        captured: list = []
        original = MockProvider.generate

        def _capture(self, request):
            captured.append(list(request.history))
            return original(self, request)

        with patch.object(MockProvider, "generate", _capture):
            runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, max_turns=1))
            for i in range(3):
                runtime.run(f"turn {i}")

        # Turn 3: provider receives history from turn 2 only
        assert captured[2][0]["content"] == "turn 1"

    def test_unlimited_provider_receives_all_history(self, tmp_path: Path) -> None:
        from unittest.mock import patch
        from agentforge.providers.mock import MockProvider

        captured: list = []
        original = MockProvider.generate

        def _capture(self, request):
            captured.append(list(request.history))
            return original(self, request)

        with patch.object(MockProvider, "generate", _capture):
            runtime = AgentRuntime.from_agent_dir(_make_agent_dir(tmp_path, max_turns=0))
            _run_n_times(runtime, 5)

        assert len(captured[-1]) == 8  # 4 prior turns = 8 messages


# ---------------------------------------------------------------------------
# Limit on disk (save + load)
# ---------------------------------------------------------------------------

class TestDiskLimit:
    def test_saved_history_respects_limit(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary", max_turns=2
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        _run_n_times(runtime, 5)

        data = json.loads((agent_dir / "history.json").read_text())
        assert len(data) == 4  # 2 turns = 4 messages

    def test_loaded_history_respects_limit(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary", max_turns=3
        )
        # First session: run 6 turns
        rt1 = AgentRuntime.from_agent_dir(agent_dir)
        _run_n_times(rt1, 6)

        # Second session with same limit: should load max 3 turns
        rt2 = AgentRuntime.from_agent_dir(agent_dir)
        assert len(rt2.history) == 6  # 3 turns = 6 messages

    def test_new_session_continues_with_most_recent_turns(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary", max_turns=2
        )
        rt1 = AgentRuntime.from_agent_dir(agent_dir)
        for i in range(5):
            rt1.run(f"msg {i}")

        rt2 = AgentRuntime.from_agent_dir(agent_dir)
        # Should have loaded the 2 most recent turns: msg 3 and msg 4
        assert rt2.history[0]["content"] == "msg 3"

    def test_limit_in_memory_matches_disk(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(
            tmp_path, memory_enabled=True, memory_type="session_summary", max_turns=2
        )
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        _run_n_times(runtime, 5)

        disk = json.loads((agent_dir / "history.json").read_text())
        assert disk == runtime.history


# ---------------------------------------------------------------------------
# Config propagation
# ---------------------------------------------------------------------------

class TestConfigPropagation:
    def test_max_turns_in_runtime_config(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path, max_turns=5)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.runtime_config.memory_max_turns == 5

    def test_default_max_turns_is_zero(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path, max_turns=0)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.runtime_config.memory_max_turns == 0

    def test_policy_default_is_truncate(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        assert runtime.runtime_config.memory_policy == "truncate"

    def test_single_turn_unaffected_by_limit(self, tmp_path: Path) -> None:
        agent_dir = _make_agent_dir(tmp_path, multi_turn=False, max_turns=1)
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        _run_n_times(runtime, 5)
        assert runtime.history == []
