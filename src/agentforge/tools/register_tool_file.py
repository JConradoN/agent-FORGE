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
    Valida, copia e registra um arquivo Python como tool no AgentForge.

    Após o registro, a tool fica disponível para todos os agentes que a
    declararem no agent.yaml. O registro persiste entre sessões via
    tool_registry/registry.yaml.

    Args:
        source_path: Caminho relativo ao AGENT_WORKDIR do arquivo Python.
        tool_name: Nome da tool (deve ser snake_case, único no registry).
        function_name: Nome da função Python pública a expor como tool.
        description: Descrição da tool para uso no schema de tools.
        input_schema: JSON schema dos parâmetros (string JSON).
        created_by: Identificação do agente criador.

    Returns:
        dict com success, tool_name, registry_path ou error.
    """
    source = Path(source_path)
    if not source.is_absolute():
        source = _workdir() / source_path

    if not source.exists():
        return {"success": False, "error": f"Arquivo não encontrado: {source}"}

    # Validação de sintaxe
    try:
        ast.parse(source.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return {"success": False, "error": f"Erro de sintaxe: {e}"}

    # Validação de importação e existência da função
    module_key = f"_agentforge_validate_{tool_name}"
    try:
        spec = importlib.util.spec_from_file_location(module_key, source)
        if spec is None or spec.loader is None:
            return {"success": False, "error": "Não foi possível carregar o módulo"}
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        func = getattr(module, function_name, None)
        if func is None:
            return {"success": False, "error": f"Função '{function_name}' não encontrada no módulo"}
    except Exception as e:
        return {"success": False, "error": f"Erro ao importar: {e}"}

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
        "message": f"Tool '{tool_name}' registrada com sucesso em tool_registry/",
    }
