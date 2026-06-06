from __future__ import annotations

import ast
import importlib.util
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_DIR = _REPO_ROOT / "tool_registry"


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def register_tool_file(
    source_path: str,
    tool_name: str,
    function_name: str,
    description: str,
    input_schema: str = "{}",
    created_by: str = "tool-builder",
) -> dict:
    """
    Validates, copies, and registers a Python file as a tool in AgentForge.

    After registration, the tool becomes available to all agents that
    declare it in agent.yaml. Registration persists between sessions via
    tool_registry/registry.yaml.

    Args:
        source_path: Path to the Python file relative to AGENT_WORKDIR.
        tool_name: Name of the tool (must be snake_case, unique in the registry).
        function_name: Name of the public Python function to expose as a tool.
        description: Description of the tool for use in the tools schema.
        input_schema: JSON schema of parameters (JSON string).
        created_by: Identification of the creator agent.

    Returns:
        dict with success, tool_name, registry_path, or error.
    """
    source = Path(source_path)
    if not source.is_absolute():
        source = _workdir() / source_path

    if not source.exists():
        return {"success": False, "error": f"File not found: {source}"}

    # Validação de sintaxe
    try:
        ast.parse(source.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return {"success": False, "error": f"Syntax error: {e}"}

    # Validação de importação e existência da função
    module_key = f"_agentforge_validate_{tool_name}"
    try:
        spec = importlib.util.spec_from_file_location(module_key, source)
        if spec is None or spec.loader is None:
            return {"success": False, "error": "Could not load the module"}
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        func = getattr(module, function_name, None)
        if func is None:
            return {"success": False, "error": f"Function '{function_name}' not found in the module"}
    except Exception as e:
        return {"success": False, "error": f"Import error: {e}"}

    # Copia para tool_registry/
    REGISTRY_DIR.mkdir(exist_ok=True)
    dest = REGISTRY_DIR / f"{tool_name}.py"
    shutil.copy2(source, dest)

    # Atualiza registry.yaml
    registry_yaml = REGISTRY_DIR / "registry.yaml"
    if registry_yaml.exists():
        data = yaml.safe_load(registry_yaml.read_text(encoding="utf-8")) or {}
    else:
        data = {}

    tools = data.get("tools") or []
    tools = [t for t in tools if t.get("name") != tool_name]
    entry = {
        "name": tool_name,
        "file": f"{tool_name}.py",
        "function": function_name,
        "description": description,
        "input_schema": input_schema,
        "created_by": created_by,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    tools.append(entry)
    data["tools"] = tools
    registry_yaml.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    # Registra no processo atual (disponível imediatamente para o agente corrente)
    from agentforge.tools.registry import register_tool
    register_tool(tool_name, func)

    return {
        "success": True,
        "tool_name": tool_name,
        "registry_path": str(dest),
        "message": f"Tool '{tool_name}' registered successfully in tool_registry/",
    }
