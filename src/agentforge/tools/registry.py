from __future__ import annotations

from typing import Any, Callable

_ToolRegistry: dict[str, Callable[[], dict[str, Any]]] = {}


def register_tool(name: str, func: Callable[[], dict[str, Any]]) -> None:
    _ToolRegistry[name] = func


def get_tool(name: str) -> Callable[[], dict[str, Any]] | None:
    return _ToolRegistry.get(name)


def execute_tool(name: str) -> dict[str, Any] | None:
    func = get_tool(name)
    if func is None:
        return None
    return func()


def list_tools() -> list[str]:
    return list(_ToolRegistry.keys())


def _register_builtin_tools() -> None:
    from agentforge.tools.system_health import collect_system_health
    from agentforge.tools.read_log_tail import read_log_tail

    register_tool("collect_system_health", collect_system_health)
    register_tool("read_log_tail", read_log_tail)


_register_builtin_tools()