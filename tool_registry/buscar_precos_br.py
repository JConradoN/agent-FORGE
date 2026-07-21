"""Busca preços de um produto em 4 lojas brasileiras via SearXNG local.

Faz uma consulta por loja (operador site:) contra a instância local do
SearXNG e agrega os resultados brutos retornados por cada engine.
"""

from __future__ import annotations

import requests

SEARXNG_URL = "http://localhost:8888/search"

LOJAS = {
    "Mercado Livre": "mercadolivre.com.br",
    "Pichau": "pichau.com.br",
    "Kabum": "kabum.com.br",
    "Terabyte": "terabyteshop.com.br",
}

TIMEOUT_S = 10


def buscar_precos_br(produto: str, searxng_url: str = SEARXNG_URL) -> list[dict]:
    """Pesquisa o preço de um produto em Mercado Livre, Pichau, Kabum e Terabyte.

    Faz uma query por loja (`<produto> site:<domínio>`) contra o SearXNG local
    e retorna os resultados brutos de cada engine, sem parsear preço — a
    extração de valor fica para uma etapa posterior.

    Args:
        produto: Nome do produto a pesquisar (ex: "i7 11700k").
        searxng_url: URL do endpoint de busca do SearXNG (default: instância local).

    Returns:
        Lista de dicts com: {loja, titulo, url, conteudo}. Lojas que falharem
        na consulta (timeout, erro HTTP, etc.) são omitidas silenciosamente do
        resultado agregado, mas não interrompem as demais.

    Raises:
        ValueError: Se produto for vazio ou apenas espaços.
    """
    if not produto or not produto.strip():
        raise ValueError("produto cannot be empty")

    resultados: list[dict] = []
    for loja, dominio in LOJAS.items():
        query = f"{produto} site:{dominio}"
        try:
            resp = requests.get(
                searxng_url,
                params={"q": query, "format": "json"},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue

        for item in data.get("results", []):
            resultados.append({
                "loja": loja,
                "titulo": item.get("title", ""),
                "url": item.get("url", ""),
                "conteudo": item.get("content", ""),
            })

    return resultados
