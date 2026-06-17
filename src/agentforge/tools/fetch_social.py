from __future__ import annotations

import subprocess

FETCH_SCRIPT = "/home/conrado/repos/producao/fox-vault/scripts/vault_ops/fetch_social.py"
FETCH_PYTHON = "/home/conrado/repos/producao/fox-vault/.venv/bin/python"
TIMEOUT = 120


def fetch_social_url(url: str, analyze: bool = True) -> str:
    """Busca URL via Scrapling (browser + cookies autenticados) e analisa com LLM local.

    Args:
        url: URL completa a buscar (LinkedIn, artigos, posts).
        analyze: Se True, retorna análise LLM. Se False, retorna texto bruto.

    Returns:
        Texto extraído ou análise, ou mensagem de erro.
    """
    cmd = [FETCH_PYTHON, FETCH_SCRIPT, url]
    if not analyze:
        cmd.append("--no-analyze")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        output = result.stdout or result.stderr or "(sem output)"
        return output
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] fetch_social_url: mais de {TIMEOUT}s para {url}"
    except Exception as exc:
        return f"[ERRO] fetch_social_url: {exc}"
