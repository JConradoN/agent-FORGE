from __future__ import annotations

from functools import partial
from typing import Any, Callable

_ToolRegistry: dict[str, Callable] = {}


def register_tool(name: str, func: Callable, **default_kwargs: Any) -> None:
    if default_kwargs:
        _ToolRegistry[name] = partial(func, **default_kwargs)
    else:
        _ToolRegistry[name] = func


def get_tool(name: str) -> Callable | None:
    return _ToolRegistry.get(name)


def execute_tool(name: str, **kwargs: Any) -> dict[str, Any] | None:
    func = get_tool(name)
    if func is None:
        return None
    try:
        if kwargs:
            if isinstance(func, partial):
                combined_kwargs = {**func.keywords, **kwargs}
                return partial(func.func, **combined_kwargs)()
            return func(**kwargs)
        return func()
    except TypeError as e:
        return {"error": str(e)}


def list_tools() -> list[str]:
    return list(_ToolRegistry.keys())


def _register_builtin_tools() -> None:
    from agentforge.tools.system_health import collect_system_health
    from agentforge.tools.read_log_tail import read_log_tail
    from agentforge.tools.vault_scan import scan_directory
    from agentforge.tools.vault_extract import extract_file_content
    from agentforge.tools.run_agent import run_agent
    from agentforge.tools.http_get import http_get
    from agentforge.tools.write_file import write_file, read_file, append_file
    from agentforge.tools.run_bash import run_bash
    from agentforge.tools.send_claudio import send_claudio

    register_tool("collect_system_health", collect_system_health)
    register_tool("read_log_tail", read_log_tail, log_path="/var/log/syslog")
    register_tool("scan_directory", scan_directory)
    register_tool("extract_file_content", extract_file_content)
    register_tool("run_agent", run_agent)
    register_tool("http_get", http_get)
    register_tool("write_file", write_file)
    register_tool("read_file", read_file)
    register_tool("append_file", append_file)
    register_tool("run_bash", run_bash)
    register_tool("send_claudio", send_claudio)

    from agentforge.tools.register_tool_file import register_tool_file
    register_tool("register_tool_file", register_tool_file)

    from agentforge.tools.tts_omnivoice import tts_omnivoice
    register_tool("tts_omnivoice", tts_omnivoice)

    from agentforge.tools.heygen_mcp import (
        heygen_credits,
        heygen_video_creator,
        heygen_upload_audio,
        heygen_list_avatars,
        heygen_get_video,
    )
    from agentforge.tools.heygen_wallet import heygen_wallet_report
    register_tool("heygen_credits", heygen_credits)
    register_tool("heygen_video_creator", heygen_video_creator)
    register_tool("heygen_upload_audio", heygen_upload_audio)
    register_tool("heygen_list_avatars", heygen_list_avatars)
    register_tool("heygen_get_video", heygen_get_video)
    register_tool("heygen_wallet_report", heygen_wallet_report)

    # Loads agent-generated tools (persists between sessions via tool_registry/)
    from agentforge.tools.dynamic_loader import load_dynamic_tools
    load_dynamic_tools()


_register_builtin_tools()