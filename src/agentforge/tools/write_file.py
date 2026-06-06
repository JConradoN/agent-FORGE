from __future__ import annotations

import os
from pathlib import Path


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def write_file(path: str, content: str) -> str:
    """Escreve content em path relativo ao AGENT_WORKDIR."""
    if not path or not path.strip():
        return "[ERRO] 'path' é obrigatório."
    target = (_workdir() / path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Arquivo escrito: {path} ({len(content)} chars)"


def read_file(path: str) -> str:
    """Lê arquivo em path relativo ao AGENT_WORKDIR. Limite 8000 chars."""
    READ_MAX = 8000
    if not path or not path.strip():
        return "[ERRO] 'path' é obrigatório."
    target = (_workdir() / path).resolve()
    if not target.exists():
        return f"[ERRO] Arquivo não encontrado: {path}"
    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > READ_MAX:
        content = content[:READ_MAX] + f"\n... [truncado — {len(content)} chars total]"
    return content


def append_file(path: str, content: str) -> str:
    """Adiciona content ao final de path relativo ao AGENT_WORKDIR."""
    if not path or not path.strip():
        return "[ERRO] 'path' é obrigatório."
    target = (_workdir() / path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(content)
    return f"Conteúdo adicionado em: {path} ({len(content)} chars)"
