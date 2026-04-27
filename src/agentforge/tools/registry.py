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
    if kwargs:
        if isinstance(func, partial):
            combined_kwargs = {**func.keywords, **kwargs}
            return partial(func.func, **combined_kwargs)()
        return func(**kwargs)
    return func()


def list_tools() -> list[str]:
    return list(_ToolRegistry.keys())


def _register_builtin_tools() -> None:
    from agentforge.tools.system_health import collect_system_health
    from agentforge.tools.read_log_tail import read_log_tail
    from agentforge.tools.vault_scan import scan_directory
    from agentforge.tools.vault_extract import extract_file_content

    register_tool("collect_system_health", collect_system_health)
    register_tool("read_log_tail", read_log_tail, log_path="/var/log/syslog")
    register_tool("scan_directory", scan_directory)
    register_tool("extract_file_content", extract_file_content)


_register_builtin_tools()