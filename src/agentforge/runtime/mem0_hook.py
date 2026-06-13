"""Fire-and-forget mem0 feed triggered at AgentRuntime.run() end.

Enabled per-agent via runtime.yaml:
    memory:
      feed_mem0: true

Runs in a daemon thread — never blocks the caller, never raises.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_MEM0_CONFIG = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen3.5:9b",
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "mem0_experiment_01",
            "embedding_model_dims": 768,
        },
    },
}


def _build_content(
    agent_id: str,
    input_text: str,
    output_text: str,
    tool_results_log: list[dict[str, Any]],
) -> str:
    parts = [f"[agent:{agent_id}]", f"user: {input_text}"]
    if tool_results_log:
        for entry in tool_results_log:
            tool = entry.get("tool", "")
            result = str(entry.get("result", ""))[:300]
            parts.append(f"tool_call:{tool} → {result}")
    parts.append(f"agent: {output_text}")
    return "\n".join(parts)


def _feed(
    agent_id: str,
    input_text: str,
    output_text: str,
    tool_results_log: list[dict[str, Any]],
) -> None:
    try:
        from mem0 import Memory  # noqa: PLC0415 — lazy import, mem0 is optional

        content = _build_content(agent_id, input_text, output_text, tool_results_log)
        m = Memory.from_config(_MEM0_CONFIG)
        m.add(content, user_id="conrado", metadata={"agent_id": agent_id, "source": "agentforge_run"})
        logger.debug("mem0_hook: fed run from agent=%s", agent_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("mem0_hook: skipped (mem0 unavailable or error): %s", exc)


def feed_async(
    agent_id: str,
    input_text: str,
    output_text: str,
    tool_results_log: list[dict[str, Any]] | None = None,
) -> None:
    """Schedule a non-blocking mem0.add() for the completed run."""
    t = threading.Thread(
        target=_feed,
        args=(agent_id, input_text, output_text, tool_results_log or []),
        daemon=True,
        name=f"mem0-hook-{agent_id}",
    )
    t.start()
