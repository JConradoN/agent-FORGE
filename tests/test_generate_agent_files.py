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
from agentforge.generators.agent_files import (
    build_agent_readme,
    build_eval_config,
    build_runtime_config,
    build_system_prompt,
    generate_agent_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_spec() -> AgentSpec:
    return AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="claudio_assistente", name="Claudio Assistente", purpose="Assistente para Telegram"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="telegram", interface="telegram"),
        tools=[ToolSpec(name="web_search"), ToolSpec(name="calc", required=True)],
        memory=MemorySpec(type="session_summary", enabled=True),
        output=OutputSpec(mode="text", format="text"),
        guardrails=GuardrailSpec(must=["usar linguagem clara"], must_not=["inventar fatos"]),
        eval=EvaluationSpec(user_score_enabled=True),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b", fallback_model="qwen3.5:9b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )


def _minimal_spec() -> AgentSpec:
    return AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="minimal", name="Minimal", purpose="Teste"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(user_score_enabled=False),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------

def test_system_prompt_contains_identity_section() -> None:
    prompt = build_system_prompt(_full_spec())
    assert "Claudio Assistente" in prompt
    assert "claudio_assistente" in prompt


def test_system_prompt_contains_objective() -> None:
    prompt = build_system_prompt(_full_spec())
    assert "Assistente para Telegram" in prompt


def test_system_prompt_contains_all_sections() -> None:
    prompt = build_system_prompt(_full_spec())
    for section in [
        "## Identity",
        "## Objective",
        "## Persona",
        "## Channel",
        "## Mandatory Behaviors",
        "## Forbidden Behaviors",
        "## Available Tools",
        "## Memory Policy",
        "## Output Format",
        "## Model and Workflow Policy",
    ]:
        assert section in prompt, f"Missing section: {section}"


def test_system_prompt_guardrails_content() -> None:
    prompt = build_system_prompt(_full_spec())
    assert "usar linguagem clara" in prompt
    assert "inventar fatos" in prompt


def test_system_prompt_tools_content() -> None:
    prompt = build_system_prompt(_full_spec())
    assert "`web_search`" in prompt
    assert "`calc`" in prompt


def test_system_prompt_no_tools_fallback() -> None:
    prompt = build_system_prompt(_minimal_spec())
    assert "No tools defined." in prompt


def test_system_prompt_memory_disabled() -> None:
    prompt = build_system_prompt(_minimal_spec())
    assert "no" in prompt


# ---------------------------------------------------------------------------
# build_runtime_config
# ---------------------------------------------------------------------------

def test_runtime_config_required_fields() -> None:
    cfg = build_runtime_config(_full_spec())
    assert cfg["runtime_version"] == "0.1"
    assert cfg["agent_id"] == "claudio_assistente"
    assert cfg["provider"] == "ollama"
    assert cfg["model"]["default"] == "gemma4:e4b"
    assert cfg["model"]["fallback"] == "qwen3.5:9b"
    assert cfg["workflow"]["mode"] == "respond_or_tool"
    assert cfg["channel"]["type"] == "telegram"
    assert cfg["memory"]["enabled"] is True
    assert cfg["memory"]["type"] == "session_summary"


def test_runtime_config_no_fallback() -> None:
    cfg = build_runtime_config(_minimal_spec())
    assert cfg["model"]["fallback"] is None


# ---------------------------------------------------------------------------
# build_eval_config
# ---------------------------------------------------------------------------

def test_eval_config_required_fields() -> None:
    cfg = build_eval_config(_full_spec())
    assert cfg["eval_version"] == "0.1"
    assert cfg["agent_id"] == "claudio_assistente"
    assert "semantic_quality" in cfg["metrics"]
    assert cfg["user_feedback"]["enabled"] is True
    assert cfg["user_feedback"]["scale"] == "0-10"


def test_eval_config_user_score_disabled() -> None:
    cfg = build_eval_config(_minimal_spec())
    assert cfg["user_feedback"]["enabled"] is False


# ---------------------------------------------------------------------------
# build_agent_readme
# ---------------------------------------------------------------------------

def test_readme_contains_agent_name_and_id() -> None:
    readme = build_agent_readme(_full_spec())
    assert "Claudio Assistente" in readme
    assert "claudio_assistente" in readme


def test_readme_contains_generated_files_list() -> None:
    readme = build_agent_readme(_full_spec())
    for fname in ["system_prompt.md", "runtime.yaml", "eval.yaml", "README.md"]:
        assert fname in readme


# ---------------------------------------------------------------------------
# generate_agent_files — functional
# ---------------------------------------------------------------------------

def test_generate_agent_files_creates_expected_artifacts(tmp_path: Path) -> None:
    spec = _full_spec()
    agent_yaml = tmp_path / "agent.yaml"
    save_agent_spec(agent_yaml, spec)

    generated = generate_agent_files(agent_yaml)
    names = {p.name for p in generated}

    assert "system_prompt.md" in names
    assert "runtime.yaml" in names
    assert "eval.yaml" in names
    assert "tools.yaml" in names
    assert "README.md" in names

    for p in generated:
        assert p.exists(), f"Arquivo não criado: {p}"


def test_generated_yamls_are_parseable(tmp_path: Path) -> None:
    spec = _full_spec()
    save_agent_spec(tmp_path / "agent.yaml", spec)
    generate_agent_files(tmp_path / "agent.yaml")

    for name in ("runtime.yaml", "eval.yaml", "tools.yaml"):
        path = tmp_path / name
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{name} não é um mapping YAML válido"


def test_generated_runtime_yaml_fields(tmp_path: Path) -> None:
    spec = _full_spec()
    save_agent_spec(tmp_path / "agent.yaml", spec)
    generate_agent_files(tmp_path / "agent.yaml")

    data = yaml.safe_load((tmp_path / "runtime.yaml").read_text())
    assert data["agent_id"] == "claudio_assistente"
    assert data["provider"] == "ollama"
    assert data["model"]["default"] == "gemma4:e4b"


def test_generated_eval_yaml_fields(tmp_path: Path) -> None:
    spec = _full_spec()
    save_agent_spec(tmp_path / "agent.yaml", spec)
    generate_agent_files(tmp_path / "agent.yaml")

    data = yaml.safe_load((tmp_path / "eval.yaml").read_text())
    assert data["agent_id"] == "claudio_assistente"
    assert data["user_feedback"]["enabled"] is True


def test_generate_overwrites_existing_files(tmp_path: Path) -> None:
    spec = _full_spec()
    save_agent_spec(tmp_path / "agent.yaml", spec)

    # Generate twice — second call should overwrite without error
    generate_agent_files(tmp_path / "agent.yaml")
    generate_agent_files(tmp_path / "agent.yaml")

    assert (tmp_path / "system_prompt.md").exists()


def test_generate_missing_spec_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        generate_agent_files(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# CLI — generate command
# ---------------------------------------------------------------------------

def test_cli_generate_command(tmp_path: Path) -> None:
    spec = _full_spec()
    agent_yaml = tmp_path / "agent.yaml"
    save_agent_spec(agent_yaml, spec)

    runner = CliRunner()
    result = runner.invoke(app, ["generate", "--path", str(agent_yaml)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "system_prompt.md").exists()
    assert (tmp_path / "runtime.yaml").exists()


def test_cli_generate_missing_file(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["generate", "--path", str(tmp_path / "ghost.yaml")])

    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# build_runtime_config — provider comes from DeploymentSpec
# ---------------------------------------------------------------------------

def test_runtime_config_uses_spec_provider() -> None:
    spec = _full_spec()
    cfg = build_runtime_config(spec)
    assert cfg["provider"] == spec.deployment.provider


def test_runtime_config_provider_mock() -> None:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="mock_agent", name="Mock Agent", purpose="Teste"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="cli"),
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="mock"),
        model_policy=ModelPolicySpec(default_model="gemma4:e4b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )
    cfg = build_runtime_config(spec)
    assert cfg["provider"] == "mock"


def test_generated_runtime_yaml_uses_spec_provider(tmp_path: Path) -> None:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="litellm_agent", name="LiteLLM Agent", purpose="Teste"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="api"),
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="litellm"),
        model_policy=ModelPolicySpec(default_model="gpt-4o"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )
    save_agent_spec(tmp_path / "agent.yaml", spec)
    generate_agent_files(tmp_path / "agent.yaml")

    data = yaml.safe_load((tmp_path / "runtime.yaml").read_text())
    assert data["provider"] == "litellm"
