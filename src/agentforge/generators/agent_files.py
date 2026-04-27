from __future__ import annotations

from pathlib import Path

import yaml

from agentforge.core.agent_models import AgentSpec
from agentforge.core.validation import validate_agent_spec

_GENERATED_FILES = ["agent.yaml", "system_prompt.md", "runtime.yaml", "eval.yaml", "tools.yaml", "README.md"]


def build_system_prompt(spec: AgentSpec) -> str:
    lines: list[str] = [
        f"# System Prompt: {spec.agent.name}",
        "",
        "## Identidade",
        "",
        f"Você é **{spec.agent.name}** (ID: `{spec.agent.id}`).",
        "",
        "## Objetivo",
        "",
        spec.agent.purpose,
        "",
        "## Persona",
        "",
        f"- **Tom:** {spec.persona.tone}",
        f"- **Estilo:** {spec.persona.style}",
    ]
    if spec.persona.personality:
        lines.append(f"- **Personalidade:** {spec.persona.personality}")

    lines += [
        "",
        "## Canal",
        "",
        f"- **Tipo:** {spec.channel.type}",
    ]
    if spec.channel.interface:
        lines.append(f"- **Interface:** {spec.channel.interface}")

    lines += ["", "## Comportamentos Obrigatórios", ""]
    if spec.guardrails.must:
        lines += [f"- {item}" for item in spec.guardrails.must]
    else:
        lines.append("Nenhum definido.")

    lines += ["", "## Comportamentos Proibidos", ""]
    if spec.guardrails.must_not:
        lines += [f"- {item}" for item in spec.guardrails.must_not]
    else:
        lines.append("Nenhum definido.")

    lines += ["", "## Tools Disponíveis", ""]
    if spec.tools:
        for tool in spec.tools:
            req_tag = " **(obrigatória)**" if tool.required else ""
            cat_tag = f" [{tool.category}]" if tool.category else ""
            status_tag = f" `{tool.status}`" if tool.status != "stable" else ""
            lines.append(f"### `{tool.name}`{req_tag}{cat_tag}{status_tag}")
            if tool.description:
                lines += ["", tool.description]
            if tool.when_to_use:
                lines += ["", f"**Quando usar:** {tool.when_to_use}"]
            if tool.when_not_to_use:
                lines += ["", f"**Quando NÃO usar:** {tool.when_not_to_use}"]
            if tool.input_schema:
                lines += ["", f"**Entrada:** `{tool.input_schema}`"]
            if tool.output_schema:
                lines += ["", f"**Saída:** `{tool.output_schema}`"]
            lines.append("")
    else:
        lines.append("Nenhuma tool definida.")

    lines += [
        "",
        "## Política de Memória",
        "",
        f"- **Habilitada:** {'sim' if spec.memory.enabled else 'não'}",
        f"- **Tipo:** {spec.memory.type}",
        "",
        "## Formato de Saída",
        "",
        f"- **Modo:** {spec.output.mode}",
    ]
    if spec.output.format:
        lines.append(f"- **Formato:** {spec.output.format}")

    lines += [
        "",
        "## Política de Modelo e Workflow",
        "",
        f"- **Modelo padrão:** {spec.model_policy.default_model}",
    ]
    if spec.model_policy.fallback_model:
        lines.append(f"- **Modelo fallback:** {spec.model_policy.fallback_model}")
    lines.append(f"- **Workflow:** {spec.workflow.mode}")
    lines.append("")

    return "\n".join(lines)


def build_runtime_config(spec: AgentSpec) -> dict:
    return {
        "runtime_version": "0.1",
        "agent_id": spec.agent.id,
        "provider": spec.deployment.provider,
        "model": {
            "default": spec.model_policy.default_model,
            "fallback": spec.model_policy.fallback_model,
        },
        "workflow": {"mode": spec.workflow.mode},
        "channel": {"type": spec.channel.type},
        "memory": {
            "enabled": spec.memory.enabled,
            "type": spec.memory.type,
            "max_turns": spec.memory.max_turns,
            "policy": spec.memory.policy,
        },
        "output": {"mode": spec.output.mode, "format": spec.output.format},
        "conversation": {"multi_turn": spec.workflow.multi_turn},
    }


def build_eval_config(spec: AgentSpec) -> dict:
    return {
        "eval_version": "0.1",
        "agent_id": spec.agent.id,
        "metrics": [
            "semantic_quality",
            "tool_use_compliance",
            "format_validity",
            "consistency",
        ],
        "user_feedback": {
            "enabled": spec.eval.user_score_enabled,
            "scale": "0-10",
        },
        "notes": spec.eval.notes,
    }


def build_tools_config(spec: AgentSpec) -> dict:
    return {
        "tools_version": "0.1",
        "agent_id": spec.agent.id,
        "tools": [
            {
                "name": t.name,
                "required": t.required,
                "description": t.description,
                "category": t.category,
                "status": t.status,
                "when_to_use": t.when_to_use,
                "when_not_to_use": t.when_not_to_use,
                "input_schema": t.input_schema,
                "output_schema": t.output_schema,
            }
            for t in spec.tools
        ],
    }


def build_agent_readme(spec: AgentSpec) -> str:
    fallback = spec.model_policy.fallback_model or "—"
    tools_list = ", ".join(f"`{t.name}`" for t in spec.tools) if spec.tools else "Nenhuma"
    memory_info = f"{spec.memory.type} (habilitada)" if spec.memory.enabled else "desabilitada"

    lines: list[str] = [
        f"# {spec.agent.name}",
        "",
        f"**ID:** `{spec.agent.id}`  ",
        f"**Versão da spec:** {spec.spec_version}",
        "",
        "## Propósito",
        "",
        spec.agent.purpose,
        "",
        "## Configuração",
        "",
        f"| Campo              | Valor                          |",
        f"|--------------------|--------------------------------|",
        f"| Canal              | {spec.channel.type}            |",
        f"| Modelo padrão      | {spec.model_policy.default_model} |",
        f"| Modelo fallback    | {fallback}                     |",
        f"| Workflow           | {spec.workflow.mode}           |",
        f"| Memória            | {memory_info}                  |",
        f"| Tools              | {tools_list}                   |",
        f"| Saída              | {spec.output.mode}             |",
        "",
        "## Arquivos gerados",
        "",
    ]
    for fname in _GENERATED_FILES:
        lines.append(f"- `{fname}`")

    lines.append("")
    return "\n".join(lines)


def generate_agent_files(agent_spec_path: str | Path) -> list[Path]:
    agent_spec_path = Path(agent_spec_path)
    spec = validate_agent_spec(agent_spec_path)
    out_dir = agent_spec_path.parent

    created: list[Path] = []

    def _write_text(name: str, content: str) -> Path:
        p = out_dir / name
        p.write_text(content, encoding="utf-8")
        return p

    def _write_yaml(name: str, data: dict) -> Path:
        p = out_dir / name
        with p.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
        return p

    created.append(_write_text("system_prompt.md", build_system_prompt(spec)))
    created.append(_write_yaml("runtime.yaml", build_runtime_config(spec)))
    created.append(_write_yaml("eval.yaml", build_eval_config(spec)))
    created.append(_write_yaml("tools.yaml", build_tools_config(spec)))
    created.append(_write_text("README.md", build_agent_readme(spec)))

    return created
