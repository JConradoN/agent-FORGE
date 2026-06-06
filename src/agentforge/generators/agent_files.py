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
        "## Identity",
        "",
        f"You are **{spec.agent.name}** (ID: `{spec.agent.id}`).",
        "",
        "## Objective",
        "",
        spec.agent.purpose,
        "",
        "## Persona",
        "",
        f"- **Tone:** {spec.persona.tone}",
        f"- **Style:** {spec.persona.style}",
    ]
    if spec.persona.personality:
        lines.append(f"- **Personality:** {spec.persona.personality}")

    lines += [
        "",
        "## Channel",
        "",
        f"- **Type:** {spec.channel.type}",
    ]
    if spec.channel.interface:
        lines.append(f"- **Interface:** {spec.channel.interface}")

    lines += ["", "## Mandatory Behaviors", ""]
    if spec.guardrails.must:
        lines += [f"- {item}" for item in spec.guardrails.must]
    else:
        lines.append("None defined.")

    lines += ["", "## Forbidden Behaviors", ""]
    if spec.guardrails.must_not:
        lines += [f"- {item}" for item in spec.guardrails.must_not]
    else:
        lines.append("None defined.")

    lines += ["", "## Available Tools", ""]
    if spec.tools:
        for tool in spec.tools:
            req_tag = " **(mandatory)**" if tool.required else ""
            cat_tag = f" [{tool.category}]" if tool.category else ""
            status_tag = f" `{tool.status}`" if tool.status != "stable" else ""
            lines.append(f"### `{tool.name}`{req_tag}{cat_tag}{status_tag}")
            if tool.description:
                lines += ["", tool.description]
            if tool.when_to_use:
                lines += ["", f"**When to use:** {tool.when_to_use}"]
            if tool.when_not_to_use:
                lines += ["", f"**When NOT to use:** {tool.when_not_to_use}"]
            if tool.input_schema:
                lines += ["", f"**Input:** `{tool.input_schema}`"]
            if tool.output_schema:
                lines += ["", f"**Output:** `{tool.output_schema}`"]
            lines.append("")
    else:
        lines.append("No tools defined.")

    lines += [
        "",
        "## Memory Policy",
        "",
        f"- **Enabled:** {'yes' if spec.memory.enabled else 'no'}",
        f"- **Type:** {spec.memory.type}",
        "",
        "## Output Format",
        "",
        f"- **Mode:** {spec.output.mode}",
    ]
    if spec.output.format:
        lines.append(f"- **Format:** {spec.output.format}")

    lines += [
        "",
        "## Model and Workflow Policy",
        "",
        f"- **Default model:** {spec.model_policy.default_model}",
    ]
    if spec.model_policy.fallback_model:
        lines.append(f"- **Fallback model:** {spec.model_policy.fallback_model}")
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
        "workflow": {
            "mode": spec.workflow.mode,
            "max_tool_cycles": spec.workflow.max_tool_cycles,
            "reflection_rounds": spec.workflow.reflection_rounds,
        },
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
    tools_list = ", ".join(f"`{t.name}`" for t in spec.tools) if spec.tools else "None"
    memory_info = f"{spec.memory.type} (enabled)" if spec.memory.enabled else "disabled"

    lines: list[str] = [
        f"# {spec.agent.name}",
        "",
        f"**ID:** `{spec.agent.id}`  ",
        f"**Spec version:** {spec.spec_version}",
        "",
        "## Purpose",
        "",
        spec.agent.purpose,
        "",
        "## Configuration",
        "",
        f"| Field              | Value                          |",
        f"|--------------------|--------------------------------|",
        f"| Channel              | {spec.channel.type}            |",
        f"| Default model      | {spec.model_policy.default_model} |",
        f"| Fallback model    | {fallback}                     |",
        f"| Workflow           | {spec.workflow.mode}           |",
        f"| Memory            | {memory_info}                  |",
        f"| Tools              | {tools_list}                   |",
        f"| Output              | {spec.output.mode}             |",
        "",
        "## Generated files",
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
