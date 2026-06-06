from __future__ import annotations

import re
from pathlib import Path

import typer

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


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return slug.strip("_") or "agent"


def _split_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _opt(raw: str) -> str | None:
    return raw.strip() or None


def _wizard_single_tool(index: int) -> ToolSpec:
    typer.echo(f"\n  Tool {index + 1}:")
    name = typer.prompt("    Tool name")
    description = _opt(typer.prompt("    Description", default=""))
    category = _opt(typer.prompt("    Category (search/compute/io/api/...)", default=""))
    required = typer.confirm("    Is it mandatory?", default=False)
    status = typer.prompt("    Status (stable/optional/experimental)", default="stable")
    when_to_use = _opt(typer.prompt("    When to use (empty to skip)", default=""))
    when_not_to_use = _opt(typer.prompt("    When NOT to use (empty to skip)", default=""))
    input_schema = _opt(typer.prompt("    Input contract (e.g.: query:str — empty to skip)", default=""))
    output_schema = _opt(typer.prompt("    Output contract (e.g.: results:list — empty to skip)", default=""))
    return ToolSpec(
        name=name,
        required=required,
        description=description,
        category=category,
        status=status or "stable",
        when_to_use=when_to_use,
        when_not_to_use=when_not_to_use,
        input_schema=input_schema,
        output_schema=output_schema,
    )


def run_agent_wizard(root: str | Path) -> Path:
    root = Path(root)

    typer.echo("\nAgent creation wizard\n")

    # --- Identity ---
    name = typer.prompt("Agent name")
    agent_id_default = _slugify(name)
    agent_id = _opt(typer.prompt("Agent ID", default=agent_id_default)) or agent_id_default
    purpose = typer.prompt("Agent purpose")

    # --- Channel and persona ---
    channel_type = typer.prompt("Channel (cli, telegram, web, api)")
    tone = typer.prompt("Tone", default="direct")
    style = typer.prompt("Style", default="technical")
    personality = _opt(typer.prompt("Personality (empty to skip)", default=""))

    # --- Model and provider ---
    default_model = typer.prompt("Default model", default="gemma4:e4b")
    fallback_model = _opt(typer.prompt("Fallback model (empty for none)", default=""))
    provider = typer.prompt("Deployment provider", default="ollama")

    # --- Workflow ---
    workflow_mode = typer.prompt("Workflow mode", default="respond_or_tool")
    multi_turn = typer.confirm("Enable multi-turn (continuous conversation)?", default=False)

    # --- Memory ---
    memory_enabled = typer.confirm("Enable memory?", default=False)
    memory_type = "none"
    memory_max_turns = 0
    memory_policy = "truncate"
    if memory_enabled:
        memory_type = typer.prompt("Memory type", default="session_summary")
        max_turns_raw = typer.prompt("History turn limit (0 = unlimited)", default="0")
        try:
            memory_max_turns = max(0, int(max_turns_raw))
        except ValueError:
            memory_max_turns = 0
        memory_policy = typer.prompt("Memory policy (truncate/summarize)", default="truncate")

    # --- Output and evaluation ---
    output_format = typer.prompt("Output format", default="text")
    user_score = typer.confirm("Enable user score?", default=False)

    # --- Guardrails ---
    must_raw = typer.prompt("Mandatory behaviors (comma-separated, empty for none)", default="")
    must_not_raw = typer.prompt("Forbidden behaviors (comma-separated, empty for none)", default="")

    # --- Tools ---
    n_tools_raw = typer.prompt("How many tools do you want to declare? (0 for none)", default="0")
    try:
        n_tools = max(0, int(n_tools_raw))
    except ValueError:
        n_tools = 0

    tools: list[ToolSpec] = []
    if n_tools > 0:
        typer.echo("\nTool declaration:")
        for i in range(n_tools):
            tools.append(_wizard_single_tool(i))

    # --- Build spec ---
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id=agent_id, name=name, purpose=purpose),
        persona=AgentPersona(tone=tone, style=style, personality=personality),
        channel=ChannelSpec(type=channel_type, interface=channel_type),
        tools=tools,
        memory=MemorySpec(
            type=memory_type,
            enabled=memory_enabled,
            max_turns=memory_max_turns,
            policy=memory_policy,
        ),
        output=OutputSpec(mode=output_format, format=output_format),
        guardrails=GuardrailSpec(
            must=_split_list(must_raw),
            must_not=_split_list(must_not_raw),
        ),
        eval=EvaluationSpec(user_score_enabled=user_score),
        deployment=DeploymentSpec(provider=provider),
        model_policy=ModelPolicySpec(default_model=default_model, fallback_model=fallback_model),
        workflow=WorkflowSpec(mode=workflow_mode, multi_turn=multi_turn),
    )

    # --- Save agent.yaml ---
    agent_yaml_path = root / "agents" / agent_id / "agent.yaml"
    save_agent_spec(agent_yaml_path, spec)
    typer.echo(f"\nagent.yaml saved to: {agent_yaml_path}")

    # --- Generate derived files ---
    from agentforge.generators.agent_files import generate_agent_files

    generated = generate_agent_files(agent_yaml_path)
    typer.echo("\nGenerated files:")
    for p in generated:
        typer.echo(f"  {p.name}")

    typer.echo(f"\nTo test the agent:")
    typer.echo(f'  agentforge run --agent-dir {agent_yaml_path.parent} --input "Hello"')

    return agent_yaml_path
