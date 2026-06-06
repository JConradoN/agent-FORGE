from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "agentforge",
    instructions=(
        "AgentForge MCP — fox-server infrastructure tools. "
        "Use collect_system_health for general diagnostics, "
        "read_log_tail to inspect logs, "
        "run_agent to execute a full AgentForge agent."
    ),
)


# ---------------------------------------------------------------------------
# Infra tools — exposed directly without going through Ollama
# ---------------------------------------------------------------------------

@mcp.tool()
def collect_system_health() -> str:
    """Collects real-time metrics from fox-server: CPU, memory, disk, GPU, and processes."""
    from agentforge.tools.system_health import collect_system_health as _fn
    return json.dumps(_fn(), indent=2, default=str)


@mcp.tool()
def read_log_tail(log_path: str = "/var/log/syslog", lines: int = 50) -> str:
    """Reads the last N lines of a system log file.

    Args:
        log_path: Absolute path of the log (default: /var/log/syslog)
        lines: Number of lines to return (default: 50)
    """
    from agentforge.tools.read_log_tail import read_log_tail as _fn
    return json.dumps(_fn(log_path=log_path, lines=lines), indent=2, default=str)


@mcp.tool()
def scan_directory(directory: str, max_files: int = 100) -> str:
    """Lists files in a directory with basic metadata.

    Args:
        directory: Path of the directory to scan
        max_files: Limit of returned files (default: 100)
    """
    from agentforge.tools.vault_scan import scan_directory as _fn
    return json.dumps(_fn(directory=directory, max_files=max_files), indent=2, default=str)


# ---------------------------------------------------------------------------
# Agent runner — executes a full AgentForge as an MCP tool
# ---------------------------------------------------------------------------

@mcp.tool()
def run_agent(input: str, agent_dir: str = "agents/lab-ops") -> str:
    """Executes a local AgentForge agent (Ollama) with the provided input.

    Args:
        input: Question or task for the agent
        agent_dir: Agent directory (default: agents/lab-ops)
    """
    from agentforge.providers.base import ProviderError
    from agentforge.runtime.engine import AgentRuntime

    try:
        runtime = AgentRuntime.from_agent_dir(Path(agent_dir))
        result = runtime.run(input)
        return result["output"]
    except ProviderError as exc:
        return f"[provider error] {exc}"
    except FileNotFoundError as exc:
        return f"[agent not found] {exc}"


def run_stdio() -> None:
    """Starts the MCP server via stdio (default for Claude Code / Claude Desktop)."""
    mcp.run(transport="stdio")


def run_http(host: str = "0.0.0.0", port: int = 8081) -> None:
    """Starts the MCP server via HTTP/SSE."""
    import uvicorn
    uvicorn.run(mcp.get_asgi_app(), host=host, port=port)
