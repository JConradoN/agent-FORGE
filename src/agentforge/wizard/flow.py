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
    name = typer.prompt("    Nome da tool")
    description = _opt(typer.prompt("    Descrição", default=""))
    category = _opt(typer.prompt("    Categoria (search/compute/io/api/...)", default=""))
    required = typer.confirm("    É obrigatória?", default=False)
    status = typer.prompt("    Status (stable/optional/experimental)", default="stable")
    when_to_use = _opt(typer.prompt("    Quando usar (vazio para pular)", default=""))
    when_not_to_use = _opt(typer.prompt("    Quando NÃO usar (vazio para pular)", default=""))
    input_schema = _opt(typer.prompt("    Contrato de entrada (ex: query:str — vazio para pular)", default=""))
    output_schema = _opt(typer.prompt("    Contrato de saída (ex: results:list — vazio para pular)", default=""))
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

    typer.echo("\nWizard de criação de agente\n")

    # --- Identidade ---
    name = typer.prompt("Nome do agente")
    agent_id_default = _slugify(name)
    agent_id = _opt(typer.prompt("ID do agente", default=agent_id_default)) or agent_id_default
    purpose = typer.prompt("Propósito do agente")

    # --- Canal e persona ---
    channel_type = typer.prompt("Canal (cli, telegram, web, api)")
    tone = typer.prompt("Tom", default="direto")
    style = typer.prompt("Estilo", default="técnico")
    personality = _opt(typer.prompt("Personalidade (vazio para pular)", default=""))

    # --- Modelo e provider ---
    default_model = typer.prompt("Modelo padrão", default="gemma4:e4b")
    fallback_model = _opt(typer.prompt("Modelo fallback (vazio para nenhum)", default=""))
    provider = typer.prompt("Provider de deployment", default="ollama")

    # --- Workflow ---
    workflow_mode = typer.prompt("Modo do workflow", default="respond_or_tool")
    multi_turn = typer.confirm("Habilitar multi-turn (conversa contínua)?", default=False)

    # --- Memória ---
    memory_enabled = typer.confirm("Habilitar memória?", default=False)
    memory_type = "none"
    memory_max_turns = 0
    memory_policy = "truncate"
    if memory_enabled:
        memory_type = typer.prompt("Tipo de memória", default="session_summary")
        max_turns_raw = typer.prompt("Limite de turnos no histórico (0 = ilimitado)", default="0")
        try:
            memory_max_turns = max(0, int(max_turns_raw))
        except ValueError:
            memory_max_turns = 0
        memory_policy = typer.prompt("Política de memória (truncate/summarize)", default="truncate")

    # --- Saída e avaliação ---
    output_format = typer.prompt("Formato de saída", default="text")
    user_score = typer.confirm("Habilitar score do usuário?", default=False)

    # --- Guardrails ---
    must_raw = typer.prompt("Comportamentos obrigatórios (vírgula, vazio para nenhum)", default="")
    must_not_raw = typer.prompt("Comportamentos proibidos (vírgula, vazio para nenhum)", default="")

    # --- Tools ---
    n_tools_raw = typer.prompt("Quantas tools você quer declarar? (0 para nenhuma)", default="0")
    try:
        n_tools = max(0, int(n_tools_raw))
    except ValueError:
        n_tools = 0

    tools: list[ToolSpec] = []
    if n_tools > 0:
        typer.echo("\nDeclaração de tools:")
        for i in range(n_tools):
            tools.append(_wizard_single_tool(i))

    # --- Construção do spec ---
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

    # --- Salvar agent.yaml ---
    agent_yaml_path = root / "agents" / agent_id / "agent.yaml"
    save_agent_spec(agent_yaml_path, spec)
    typer.echo(f"\nagent.yaml salvo em: {agent_yaml_path}")

    # --- Gerar arquivos derivados ---
    from agentforge.generators.agent_files import generate_agent_files

    generated = generate_agent_files(agent_yaml_path)
    typer.echo("\nArquivos gerados:")
    for p in generated:
        typer.echo(f"  {p.name}")

    typer.echo(f"\nPara testar o agente:")
    typer.echo(f'  agentforge run --agent-dir {agent_yaml_path.parent} --input "Olá"')

    return agent_yaml_path
