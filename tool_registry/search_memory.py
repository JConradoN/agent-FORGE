"""Memory search tool for fox-server agent-mesh shared memory.

Primary backend: mem0 semantic search (Qdrant + nomic-embed-text).
Fallback: SQLite LIKE search on agent-mesh shared_memory table.

mem0 is used when Qdrant is reachable and returns results with score >= MEM0_THRESHOLD.
If mem0 is unavailable or returns nothing, falls back to SQLite transparently.
"""

import os
import sqlite3
from typing import Optional

MEM0_THRESHOLD = 0.50
MEM0_TOP_K = 5
MEM0_COLLECTION = "mem0_experiment_01"
OLLAMA_URL = "http://localhost:11434"

_MEM0_CONFIG = {
    "llm": {
        "provider": "ollama",
        "config": {"model": "qwen3.5:9b", "ollama_base_url": OLLAMA_URL},
    },
    "embedder": {
        "provider": "ollama",
        "config": {"model": "nomic-embed-text", "ollama_base_url": OLLAMA_URL},
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
            "collection_name": MEM0_COLLECTION,
            "embedding_model_dims": 768,
        },
    },
}


def _search_mem0(query: str) -> list[dict]:
    """Tries semantic search via mem0. Returns [] on any failure."""
    try:
        from mem0 import Memory
        m = Memory.from_config(_MEM0_CONFIG)
        raw = m.search(query, filters={"user_id": "conrado"}, top_k=MEM0_TOP_K)
        hits = raw.get("results", [])
        results = []
        for h in hits:
            score = h.get("score", 0)
            if score < MEM0_THRESHOLD:
                continue
            mem_id = h.get("id", "")
            meta = h.get("metadata") or {}
            results.append({
                "key": f"mem0:{str(mem_id)[:8]}",
                "value_preview": str(h.get("memory", ""))[:200],
                "agent": meta.get("agent_id", "claude-code"),
                "updated_at": h.get("updated_at", "unknown"),
                "score": round(score, 3),
                "source": "mem0",
            })
        return results
    except Exception:
        return []


def _get_default_db_path() -> str:
    home_dir = os.path.expanduser("~")
    if not home_dir or home_dir == "~":
        raise RuntimeError("Unable to determine user's home directory")
    return os.path.join(home_dir, ".agent-mesh", "state.db")


def _connect_to_db(db_path: str) -> sqlite3.Connection | None:
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _search_sqlite(query: str, db_path: str) -> list[dict]:
    """LIKE search on agent-mesh shared_memory. Returns [] if DB absent or table missing."""
    conn = _connect_to_db(db_path)
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        search_pattern = f"%{query}%"
        sql_query = """
            SELECT
                key,
                substr(value, 1, 200) as value_preview,
                agent,
                datetime(updated_at, 'unixepoch') as updated_at
            FROM shared_memory
            WHERE (key LIKE ? ESCAPE '\\' OR value LIKE ? ESCAPE '\\')
            ORDER BY
                CASE WHEN key LIKE ? THEN 1 ELSE 3 END,
                CASE WHEN value LIKE ? THEN 2 ELSE 4 END DESC,
                updated_at DESC
            LIMIT 3;
        """
        cursor.execute(sql_query, (search_pattern, search_pattern,
                                   f"%{query}%", search_pattern))
        rows = cursor.fetchall()
        return [
            {
                "key": row["key"],
                "value_preview": row["value_preview"],
                "agent": row["agent"],
                "updated_at": row["updated_at"],
                "source": "sqlite",
            }
            for row in rows
        ]
    except Exception:
        return []
    finally:
        conn.close()


def search_memory(query: str, db_path: Optional[str] = None) -> list[dict]:
    """Searches agent memory using semantic search (mem0) with SQLite LIKE fallback.

    Primary: mem0 semantic search over all Claude Code sessions (Qdrant + nomic-embed-text).
    Fallback: LIKE search on agent-mesh SQLite shared_memory table.

    Args:
        query: Search term (cannot be empty).
        db_path: Optional path to the SQLite database. Defaults to ~/.agent-mesh/state.db.

    Returns:
        List of dicts with: {key, value_preview, agent, updated_at, source, score?}.
        Returns an empty list if both backends return nothing.

    Raises:
        ValueError: If the query is empty or just whitespace.
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty")

    actual_db_path = db_path if db_path else _get_default_db_path()

    # When db_path is explicitly provided, skip mem0 (test mode / explicit override).
    # When using the default path, try mem0 first for semantic recall.
    if db_path is None:
        mem0_results = _search_mem0(query)
        if mem0_results:
            return mem0_results

    return _search_sqlite(query, actual_db_path)
