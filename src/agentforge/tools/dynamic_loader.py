from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

# Repo root = 4 parents above src/agentforge/tools/dynamic_loader.py
_REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_DIR = _REPO_ROOT / "tool_registry"


def load_dynamic_tools() -> list[str]:
    """Loads tools registered in tool_registry/registry.yaml into the live _ToolRegistry."""
    from agentforge.tools.registry import register_tool

    registry_yaml = REGISTRY_DIR / "registry.yaml"
    if not registry_yaml.exists():
        return []

    try:
        data = yaml.safe_load(registry_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        return []

    tools = data.get("tools") or []
    loaded: list[str] = []

    for entry in tools:
        name = entry.get("name", "")
        file_rel = entry.get("file", f"{name}.py")
        func_name = entry.get("function", name)
        file_path = REGISTRY_DIR / file_rel

        if not file_path.exists():
            continue

        module_key = f"_agentforge_dynamic_{name}"
        try:
            spec = importlib.util.spec_from_file_location(module_key, file_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_key] = module
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            func = getattr(module, func_name, None)
            if func is None:
                continue
            register_tool(name, func)
            loaded.append(name)
        except Exception:
            pass

    return loaded
