#!/usr/bin/env python3
"""
V5 — Fuzzy Path Resolution Benchmark

Compara _extract_filename_intent (atual, regex-only) com
_extract_filename_intent_fuzzy (experimental) para queries reais
do vault-pilot staging.

Uso (a partir da raiz do projeto):
    python scripts/run_v5_path_benchmark.py
"""

import json
from datetime import datetime
from pathlib import Path

from agentforge.runtime.engine import (
    AgentRuntime,
    _extract_filename_intent_fuzzy,
)
from agentforge.tools.vault_scan import scan_directory

AGENT_DIR = "agents/vault-pilot"
RESULTS_DIR = Path("results/benchmarks/V5")

TEST_QUERIES = [
    # --- Casos com path exato / quase-exato ---
    {
        "id": "exact_full_path",
        "utterance": (
            "Use as ferramentas disponíveis para analisar o arquivo "
            "CONRADO/GERAL/Contrato Conrado Nogueira.pdf e descrever o conteúdo."
        ),
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
    {
        "id": "basename_with_extension",
        "utterance": (
            "Analise o arquivo Contrato Conrado Nogueira.pdf e me traga um resumo."
        ),
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
    # --- Casos com aspas ---
    {
        "id": "basename_quoted_double",
        "utterance": (
            'Analise o contrato "Contrato Conrado Nogueira.pdf" que está no staging.'
        ),
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
    {
        "id": "basename_quoted_single",
        "utterance": (
            "Analise o contrato 'Contrato Conrado Nogueira' que está na pasta do Conrado."
        ),
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
    # --- Casos com nome curto / paráfrase ---
    {
        "id": "short_name_conrado",
        "utterance": "Analise o contrato do Conrado.",
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
    {
        "id": "short_name_nogueira",
        "utterance": "Extraia o documento do Nogueira.",
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
    # --- Casos de ausência / sem match esperado ---
    {
        "id": "nonexistent_file",
        "utterance": "Analise o arquivo RelatorioFinanceiro2024.pdf.",
        "expected_path": None,  # arquivo não existe no staging
    },
    # --- Casos para outros diretórios (se existirem arquivos de EMILIA ou outros) ---
    {
        "id": "emilia_rg",
        "utterance": "Preciso ver o RG da Emilia.",
        "expected_path": None,  # será resolvido dinamicamente se existir
    },
    # --- Variações de capitalização ---
    {
        "id": "uppercase_query",
        "utterance": "ANALISE O CONTRATO CONRADO NOGUEIRA",
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
    # --- Nome parcial sem extensão ---
    {
        "id": "partial_name_no_ext",
        "utterance": "Me fale sobre o arquivo contrato nogueira",
        "expected_path": "CONRADO/GERAL/Contrato Conrado Nogueira.pdf",
    },
]


def get_staging_paths() -> list[str]:
    """Retorna lista de paths relativos disponíveis no staging."""
    result = scan_directory()
    if "error" in result:
        print(f"AVISO: scan_directory retornou erro: {result.get('message')}")
        return []
    files = result.get("files", [])
    paths = [f["path"] for f in files if "path" in f]
    return paths


def run_current_intent(engine: AgentRuntime, utterance: str) -> str | None:
    """Invoca o método de produção _extract_filename_intent."""
    return engine._extract_filename_intent(utterance)


def run_v5_benchmark():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d-%H%M")

    engine = AgentRuntime.from_agent_dir(AGENT_DIR)

    file_paths = get_staging_paths()
    print(f"Paths no staging: {len(file_paths)}")
    for p in file_paths:
        print(f"  - {p}")
    print()

    # Resolve expected_path dinamicamente para queries sem path fixo
    emilia_rg_candidates = [p for p in file_paths if "emilia" in p.lower() and "rg" in p.lower()]
    for q in TEST_QUERIES:
        if q["id"] == "emilia_rg" and emilia_rg_candidates:
            q["expected_path"] = emilia_rg_candidates[0]

    results = []
    for query in TEST_QUERIES:
        utterance = query["utterance"]
        expected = query["expected_path"]

        # Método atual (regex)
        current_result = run_current_intent(engine, utterance)

        # Método fuzzy (experimental V5)
        fuzzy_result = _extract_filename_intent_fuzzy(utterance, file_paths)
        fuzzy_resolved = fuzzy_result["resolved_path"]

        current_correct = current_result == expected
        fuzzy_correct = fuzzy_resolved == expected

        result = {
            "id": query["id"],
            "utterance": utterance,
            "expected_path": expected,
            "current_resolved": current_result,
            "current_correct": current_correct,
            "fuzzy_match_type": fuzzy_result["match_type"],
            "fuzzy_resolved_path": fuzzy_resolved,
            "fuzzy_correct": fuzzy_correct,
            "fuzzy_top_candidates": fuzzy_result["candidates"][:3],
        }
        results.append(result)

    # Salvar JSON
    out_file = RESULTS_DIR / f"V5-path-benchmark-{date_str}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Resumo no stdout
    total = len(results)
    current_hits = sum(1 for r in results if r["current_correct"])
    fuzzy_hits = sum(1 for r in results if r["fuzzy_correct"])
    fuzzy_ambiguous = sum(1 for r in results if r["fuzzy_match_type"] == "ambiguous")
    fuzzy_none = sum(1 for r in results if r["fuzzy_match_type"] == "none")

    print(f"\n{'='*80}")
    print(f"{'id':<28} {'current':>8} {'fuzzy_type':<12} {'fuzzy':>7} {'match?'}")
    print(f"{'-'*80}")
    for r in results:
        cur_mark = "OK " if r["current_correct"] else "ERR"
        fuz_mark = "OK " if r["fuzzy_correct"] else "ERR"
        print(
            f"{r['id']:<28} "
            f"[{cur_mark}]  "
            f"{r['fuzzy_match_type']:<12} "
            f"[{fuz_mark}]  "
            f"{r['fuzzy_resolved_path'] or '(none)'!r}"
        )
    print(f"{'='*80}")
    print(f"Resultados: {total} queries")
    print(f"  current (regex):  {current_hits}/{total} corretos")
    print(f"  fuzzy:            {fuzzy_hits}/{total} corretos  |  "
          f"ambiguous={fuzzy_ambiguous}  none={fuzzy_none}")
    print(f"\nJSON salvo em: {out_file}")

    # Casos onde fuzzy errou ou foi ambiguous
    problems = [r for r in results if not r["fuzzy_correct"]]
    if problems:
        print(f"\n--- Casos problemáticos ({len(problems)}) ---")
        for r in problems:
            print(f"\n  id: {r['id']}")
            print(f"  utterance: {r['utterance'][:80]!r}")
            print(f"  expected:  {r['expected_path']!r}")
            print(f"  resolved:  {r['fuzzy_resolved_path']!r}  ({r['fuzzy_match_type']})")
            if r["fuzzy_top_candidates"]:
                print(f"  top-3 candidates:")
                for c in r["fuzzy_top_candidates"]:
                    print(f"    score={c['score']:.3f}  {c['reason']:<20}  {c['path']!r}")

    return results


if __name__ == "__main__":
    run_v5_benchmark()
