from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "agentforge",
    instructions=(
        "AgentForge MCP — ferramentas de infraestrutura do fox-server. "
        "Use collect_system_health para diagnóstico geral, "
        "read_log_tail para inspecionar logs, "
        "run_agent para executar um agente AgentForge completo."
    ),
)


# ---------------------------------------------------------------------------
# Infra tools — expostos diretamente sem passar pelo Ollama
# ---------------------------------------------------------------------------

@mcp.tool()
def collect_system_health() -> str:
    """Coleta métricas em tempo real do fox-server: CPU, memória, disco, GPU e processos."""
    from agentforge.tools.system_health import collect_system_health as _fn
    return json.dumps(_fn(), indent=2, default=str)


@mcp.tool()
def read_log_tail(log_path: str = "/var/log/syslog", lines: int = 50) -> str:
    """Lê as últimas N linhas de um arquivo de log do sistema.

    Args:
        log_path: Caminho absoluto do log (default: /var/log/syslog)
        lines: Número de linhas a retornar (default: 50)
    """
    from agentforge.tools.read_log_tail import read_log_tail as _fn
    return json.dumps(_fn(log_path=log_path, lines=lines), indent=2, default=str)


@mcp.tool()
def scan_directory(directory: str, max_files: int = 100) -> str:
    """Lista arquivos de um diretório com metadados básicos.

    Args:
        directory: Caminho do diretório a escanear
        max_files: Limite de arquivos retornados (default: 100)
    """
    from agentforge.tools.vault_scan import scan_directory as _fn
    return json.dumps(_fn(directory=directory, max_files=max_files), indent=2, default=str)


# ---------------------------------------------------------------------------
# Agent runner — executa um AgentForge completo como MCP tool
# ---------------------------------------------------------------------------

@mcp.tool()
def run_agent(input: str, agent_dir: str = "agents/lab-ops") -> str:
    """Executa um agente AgentForge local (Ollama) com o input fornecido.

    Args:
        input: Pergunta ou tarefa para o agente
        agent_dir: Diretório do agente (default: agents/lab-ops)
    """
    from agentforge.providers.base import ProviderError
    from agentforge.runtime.engine import AgentRuntime

    try:
        runtime = AgentRuntime.from_agent_dir(Path(agent_dir))
        result = runtime.run(input)
        return result["output"]
    except ProviderError as exc:
        return f"[erro de provider] {exc}"
    except FileNotFoundError as exc:
        return f"[agente não encontrado] {exc}"


def run_stdio() -> None:
    """Inicia o servidor MCP via stdio (padrão para Claude Code / Claude Desktop)."""
    mcp.run(transport="stdio")


def run_http(host: str = "0.0.0.0", port: int = 8081) -> None:
    """Inicia o servidor MCP via HTTP/SSE."""
    import uvicorn
    uvicorn.run(mcp.get_asgi_app(), host=host, port=port)
