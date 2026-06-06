from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml

from agentforge.core.agent_models import AgentSpec, DeploymentSpec
from agentforge.core.validation import save_agent_spec, validate_agent_spec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_spec() -> AgentSpec:
    from agentforge.core.agent_models import (
        AgentIdentity, AgentPersona, ChannelSpec, EvaluationSpec,
        GuardrailSpec, MemorySpec, ModelPolicySpec, OutputSpec,
        ToolSpec, WorkflowSpec,
    )
    return AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="test_agent", name="Test Agent", purpose="Teste"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )


def _make_wizard_mocks(
    monkeypatch: pytest.MonkeyPatch,
    prompts: list[str],
    confirms: list[bool],
) -> None:
    p_iter = iter(prompts)
    c_iter = iter(confirms)
    monkeypatch.setattr(typer, "prompt", lambda *a, **kw: next(p_iter))
    monkeypatch.setattr(typer, "confirm", lambda *a, **kw: next(c_iter))
    monkeypatch.setattr(typer, "echo", lambda *a, **kw: None)


# ---------------------------------------------------------------------------
# validate_agent_spec
# ---------------------------------------------------------------------------

def test_validate_agent_spec_from_yaml(tmp_path: Path) -> None:
    spec = _make_valid_spec()
    agent_yaml = tmp_path / "agent.yaml"
    save_agent_spec(agent_yaml, spec)

    loaded = validate_agent_spec(agent_yaml)
    assert isinstance(loaded, AgentSpec)
    assert loaded.agent.id == "test_agent"
    assert loaded.agent.name == "Test Agent"
    assert loaded.memory.enabled is False


def test_validate_agent_spec_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_agent_spec(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# save_agent_spec
# ---------------------------------------------------------------------------

def test_save_agent_spec_creates_file_and_dirs(tmp_path: Path) -> None:
    spec = _make_valid_spec()
    nested_path = tmp_path / "agents" / "test_agent" / "agent.yaml"
    save_agent_spec(nested_path, spec)

    assert nested_path.exists()
    raw = yaml.safe_load(nested_path.read_text())
    assert raw["agent"]["id"] == "test_agent"
    assert raw["spec_version"] == "0.1"


def test_save_and_reload_roundtrip(tmp_path: Path) -> None:
    spec = _make_valid_spec()
    path = tmp_path / "agent.yaml"
    save_agent_spec(path, spec)

    reloaded = validate_agent_spec(path)
    assert reloaded.model_dump() == spec.model_dump()


# ---------------------------------------------------------------------------
# run_agent_wizard — minimal agent (no memory, no tools)
# ---------------------------------------------------------------------------

_MINIMAL_PROMPTS = [
    "Meu Agente",       # name
    "meu_agente",       # id
    "Agente simples",   # purpose
    "cli",              # channel
    "direto",           # tone
    "técnico",          # style
    "",                 # personality (skip)
    "gemma4:e4b",       # model
    "",                 # fallback (none)
    "ollama",           # provider
    "respond_or_tool",  # workflow_mode
    # C: multi_turn → False
    # C: memory → False
    "text",             # output_format
    # C: user_score → False
    "",                 # must
    "",                 # must_not
    "0",                # n_tools
]
_MINIMAL_CONFIRMS = [False, False, False]  # multi_turn, memory, user_score


def test_wizard_minimal_creates_agent_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _MINIMAL_PROMPTS, _MINIMAL_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    result = run_agent_wizard(tmp_path)
    assert result == tmp_path / "agents" / "meu_agente" / "agent.yaml"
    assert result.exists()


def test_wizard_minimal_spec_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _MINIMAL_PROMPTS, _MINIMAL_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    result = run_agent_wizard(tmp_path)
    spec = validate_agent_spec(result)
    assert spec.memory.enabled is False
    assert spec.memory.type == "none"
    assert spec.workflow.multi_turn is False
    assert spec.tools == []
    assert spec.guardrails.must == []


def test_wizard_minimal_generates_derived_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _MINIMAL_PROMPTS, _MINIMAL_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    agent_yaml = run_agent_wizard(tmp_path)
    agent_dir = agent_yaml.parent
    assert (agent_dir / "runtime.yaml").exists()
    assert (agent_dir / "system_prompt.md").exists()
    assert (agent_dir / "tools.yaml").exists()
    assert (agent_dir / "eval.yaml").exists()


# ---------------------------------------------------------------------------
# run_agent_wizard — complex agent (memory + multi-turn + 1 rich tool)
# ---------------------------------------------------------------------------

# Prompt sequence (26 prompts + 4 confirms):
_COMPLEX_PROMPTS = [
    "Claudio Assistente",           # name
    "claudio_assistente",           # id
    "Assistente para Telegram",     # purpose
    "telegram",                     # channel
    "direto",                       # tone
    "técnico",                      # style
    "prestativo e objetivo",        # personality
    "gemma4:e4b",                   # model
    "qwen3.5:9b",                   # fallback
    "ollama",                       # provider
    "respond_or_tool",              # workflow_mode
    # C: multi_turn → True
    # C: memory → True
    "session_summary",              # memory_type
    "20",                           # max_turns
    "summarize",                    # policy
    "text",                         # output_format
    # C: user_score → True
    "usar linguagem clara",         # must
    "inventar fatos",               # must_not
    "1",                            # n_tools
    # --- Tool 1 ---
    "web_search",                   # tool name
    "Busca informações na internet",# tool description
    "search",                       # category
    # C: required → False
    "stable",                       # status
    "Quando precisar de informações atuais ou notícias",  # when_to_use
    "Para fatos históricos bem conhecidos",               # when_not_to_use
    "query: str, max_results: int = 10",                  # input_schema
    "results: list[str], total: int",                     # output_schema
]
_COMPLEX_CONFIRMS = [True, True, True, False]  # multi_turn, memory, user_score, tool.required


def test_wizard_complex_creates_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    result = run_agent_wizard(tmp_path)
    assert result.exists()


def test_wizard_complex_memory_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    spec = validate_agent_spec(run_agent_wizard(tmp_path))
    assert spec.memory.enabled is True
    assert spec.memory.type == "session_summary"
    assert spec.memory.max_turns == 20
    assert spec.memory.policy == "summarize"


def test_wizard_complex_multi_turn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    spec = validate_agent_spec(run_agent_wizard(tmp_path))
    assert spec.workflow.multi_turn is True


def test_wizard_complex_persona(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    spec = validate_agent_spec(run_agent_wizard(tmp_path))
    assert spec.persona.personality == "prestativo e objetivo"


def test_wizard_complex_tool_basic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    spec = validate_agent_spec(run_agent_wizard(tmp_path))
    assert len(spec.tools) == 1
    tool = spec.tools[0]
    assert tool.name == "web_search"
    assert tool.required is False
    assert tool.description == "Busca informações na internet"


def test_wizard_complex_tool_rich_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    spec = validate_agent_spec(run_agent_wizard(tmp_path))
    tool = spec.tools[0]
    assert tool.category == "search"
    assert tool.status == "stable"
    assert tool.when_to_use is not None
    assert "atuais" in tool.when_to_use
    assert tool.when_not_to_use is not None
    assert tool.input_schema is not None
    assert "query" in tool.input_schema
    assert tool.output_schema is not None
    assert "results" in tool.output_schema


def test_wizard_complex_generates_runtime_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    agent_yaml = run_agent_wizard(tmp_path)
    runtime = yaml.safe_load((agent_yaml.parent / "runtime.yaml").read_text())
    assert runtime["agent_id"] == "claudio_assistente"
    assert runtime["provider"] == "ollama"
    assert runtime["conversation"]["multi_turn"] is True
    assert runtime["memory"]["max_turns"] == 20
    assert runtime["memory"]["policy"] == "summarize"


def test_wizard_complex_system_prompt_has_tool_details(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    agent_yaml = run_agent_wizard(tmp_path)
    prompt_text = (agent_yaml.parent / "system_prompt.md").read_text()
    assert "web_search" in prompt_text
    assert "search" in prompt_text
    assert "query" in prompt_text
    assert "When to use" in prompt_text or "when to use" in prompt_text.lower()


def test_wizard_complex_tools_yaml_has_rich_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _COMPLEX_PROMPTS, _COMPLEX_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    agent_yaml = run_agent_wizard(tmp_path)
    tools_data = yaml.safe_load((agent_yaml.parent / "tools.yaml").read_text())
    tool = tools_data["tools"][0]
    assert tool["name"] == "web_search"
    assert tool["category"] == "search"
    assert tool["input_schema"] is not None
    assert tool["when_to_use"] is not None


# ---------------------------------------------------------------------------
# Generated agent can be loaded by AgentRuntime
# ---------------------------------------------------------------------------

def test_wizard_generated_agent_loads_in_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_wizard_mocks(monkeypatch, _MINIMAL_PROMPTS, _MINIMAL_CONFIRMS)
    from agentforge.wizard.flow import run_agent_wizard
    from agentforge.core.agent_models import DeploymentSpec as DS
    agent_yaml = run_agent_wizard(tmp_path)

    # Patch provider to mock so we don't need Ollama
    raw = yaml.safe_load(agent_yaml.read_text())
    raw["deployment"] = {"provider": "mock"}
    agent_yaml.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    # Rebuild runtime.yaml with mock provider
    import yaml as _yaml
    runtime_path = agent_yaml.parent / "runtime.yaml"
    rt = _yaml.safe_load(runtime_path.read_text())
    rt["provider"] = "mock"
    runtime_path.write_text(_yaml.safe_dump(rt, allow_unicode=True), encoding="utf-8")

    from agentforge.runtime.engine import AgentRuntime
    runtime = AgentRuntime.from_agent_dir(agent_yaml.parent)
    result = runtime.run("Olá")
    assert result["agent_id"] == "meu_agente"
    assert "MOCK_PROVIDER_RESPONSE" in result["output"]


# ---------------------------------------------------------------------------
# ToolSpec backward compatibility
# ---------------------------------------------------------------------------

def test_tool_spec_minimal_still_works() -> None:
    from agentforge.core.agent_models import ToolSpec
    t = ToolSpec(name="web_search")
    assert t.required is False
    assert t.description is None
    assert t.category is None
    assert t.status == "stable"
    assert t.when_to_use is None
    assert t.when_not_to_use is None
    assert t.input_schema is None
    assert t.output_schema is None


def test_tool_spec_full_fields() -> None:
    from agentforge.core.agent_models import ToolSpec
    t = ToolSpec(
        name="calc",
        required=True,
        description="Calculadora",
        category="compute",
        status="experimental",
        when_to_use="Para cálculos",
        when_not_to_use="Para texto",
        input_schema="expression: str",
        output_schema="result: float",
    )
    assert t.name == "calc"
    assert t.category == "compute"
    assert t.status == "experimental"
    assert t.input_schema == "expression: str"


def test_old_yaml_with_minimal_tool_loads(tmp_path: Path) -> None:
    raw = {
        "spec_version": "0.1",
        "agent": {"id": "old", "name": "Old", "purpose": "Legacy"},
        "persona": {"tone": "direto", "style": "técnico"},
        "channel": {"type": "cli"},
        "tools": [{"name": "web_search", "required": False, "description": None}],
        "memory": {"type": "none", "enabled": False},
        "output": {"mode": "text"},
        "guardrails": {"must": [], "must_not": [], "optional": []},
        "eval": {"user_score_enabled": False},
        "model_policy": {"default_model": "gemma4:e4b"},
        "workflow": {"mode": "respond_or_tool"},
    }
    p = tmp_path / "agent.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    spec = validate_agent_spec(p)
    assert spec.tools[0].name == "web_search"
    assert spec.tools[0].category is None  # new field defaults to None


# ---------------------------------------------------------------------------
# DeploymentSpec backward compat
# ---------------------------------------------------------------------------

def test_deployment_default_is_ollama() -> None:
    spec = _make_valid_spec()
    assert spec.deployment.provider == "ollama"


def test_backward_compat_spec_without_deployment(tmp_path: Path) -> None:
    raw = {
        "spec_version": "0.1",
        "agent": {"id": "old_agent", "name": "Old Agent", "purpose": "Legacy"},
        "persona": {"tone": "direto", "style": "técnico"},
        "channel": {"type": "cli"},
        "memory": {"type": "none", "enabled": False},
        "output": {"mode": "text"},
        "guardrails": {"must": [], "must_not": [], "optional": []},
        "eval": {"user_score_enabled": False},
        "model_policy": {"default_model": "gemma4:e4b"},
        "workflow": {"mode": "respond_or_tool"},
    }
    agent_yaml = tmp_path / "agent.yaml"
    agent_yaml.write_text(yaml.safe_dump(raw), encoding="utf-8")
    spec = validate_agent_spec(agent_yaml)
    assert spec.deployment.provider == "ollama"
