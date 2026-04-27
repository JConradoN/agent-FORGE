#!/usr/bin/env python3
"""
V3 — History Corruption Benchmark

Testa se o bug de "modelo inventa tool calls" reaparece com histórico
sintético corrompido (turns consecutivos com assistant.content==""),
e se clean_history + diferentes formatos de injeção eliminam o bug.

Uso (a partir da raiz do projeto):
    python scripts/run_v3_benchmark.py
"""

import json
import unicodedata
from datetime import datetime
from pathlib import Path

from agentforge.runtime.engine import AgentRuntime
from agentforge.tools.vault_extract import extract_file_content

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

AGENT_DIR = "agents/vault-pilot"
RESULTS_DIR = Path("results/benchmarks/V3")

TEST_DOCUMENT_PATH = (
    "/home/conrado/testes/vault/input/CONRADO/GERAL/Contrato Conrado Nogueira.pdf"
)

# Ground truth com normalização de acento no compute_faithfulness_v3
GROUND_TRUTH = {
    "empresa": "CEREJA E OLIVEIRA",
    "cnpj":    "37.262",
    "cidade":  "Macapá",
    "tipo":    "prestação de serviços",
}

PROMPT = (
    "Descreva o conteúdo do documento. Inclua: nome das partes, "
    "objeto do contrato, valor (se houver), data e quaisquer outros "
    "dados relevantes presentes no texto."
)

# (history_scenario, injection_mode, apply_clean, label)
CONFIGS_V3 = [
    # baseline limpo
    ("clean",  "current_tag",        False, "clean_current"),
    # dirty sem limpeza (deve reproduzir o bug)
    ("dirty1", "current_tag",        False, "dirty1_current"),
    ("dirty2", "current_tag",        False, "dirty2_current"),
    ("dirty3", "current_tag",        False, "dirty3_current"),
    # dirty com limpeza de history (correção candidata)
    ("dirty1", "current_tag",        True,  "dirty1_current_cleaned"),
    ("dirty2", "current_tag",        True,  "dirty2_current_cleaned"),
    ("dirty3", "current_tag",        True,  "dirty3_current_cleaned"),
    # dirty + formatos alternativos, com e sem limpeza
    ("dirty2", "instruction_strong", False, "dirty2_instruction"),
    ("dirty2", "instruction_strong", True,  "dirty2_instruction_cleaned"),
    ("dirty2", "plain_block",        True,  "dirty2_plain_cleaned"),
]


# ---------------------------------------------------------------------------
# Histórico sintético
# ---------------------------------------------------------------------------

def build_synthetic_history(scenario: str, tool_prefix: str = "") -> list[dict]:
    """
    Constrói históricos sintéticos para reproduzir o bug.

    scenario:
      "clean"   — history vazio
      "dirty1"  — 2 turns assistant="" antes da consulta
      "dirty2"  — 3 turns assistant="" antes da consulta final
      "dirty3"  — dirty2 + turn inicial com scan output grande (simula contexto acumulado)
    """
    def turn(role: str, content: str) -> dict:
        return {"role": role, "content": content}

    if scenario == "clean":
        return []

    if scenario == "dirty1":
        return [
            turn("user",      "Analise o contrato"),
            turn("assistant", ""),
            turn("user",      "Analise o contrato novamente"),
            turn("assistant", ""),
        ]

    if scenario == "dirty2":
        return [
            turn("user",      "Liste os arquivos"),
            turn("assistant", ""),
            turn("user",      "Extraia o contrato"),
            turn("assistant", ""),
            turn("user",      "Analise o contrato"),
            turn("assistant", ""),
        ]

    if scenario == "dirty3":
        fake_scan = json.dumps({
            "file_count": 50,
            "files": [{"path": f"CONRADO/GERAL/doc{i}.pdf"} for i in range(50)],
        })
        scan_content = f"{tool_prefix}{fake_scan}" if tool_prefix else fake_scan
        return [
            turn("user",      "Liste os arquivos"),
            turn("assistant", scan_content),
            turn("user",      "Extraia o contrato"),
            turn("assistant", ""),
            turn("user",      "Analise o contrato"),
            turn("assistant", ""),
        ]

    return []


# ---------------------------------------------------------------------------
# Limpeza de histórico (correção candidata para produção)
# ---------------------------------------------------------------------------

def clean_history(history: list[dict], max_turns: int = 6) -> list[dict]:
    """
    Remove turns em que assistant.content é vazio e limita a max_turns.

    Esta é a correção candidata:
      - não envia respostas vazias ao modelo,
      - corta o histórico para evitar contexto excessivo.
    """
    cleaned = [
        t for t in history
        if not (
            t.get("role") == "assistant"
            and str(t.get("content", "")).strip() == ""
        )
    ]
    return cleaned[-max_turns:]


# ---------------------------------------------------------------------------
# Faithfulness com normalização de acento (corrige bug do V2)
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def compute_faithfulness_v3(response: str, ground_truth: dict) -> dict:
    response_norm = _normalize(response)
    hits = {}
    for key, value in ground_truth.items():
        hits[key] = _normalize(value) in response_norm

    fact_hits = sum(hits.values())
    total_facts = len(ground_truth)

    tool_call_attempt = any(
        marker in response.lower()
        for marker in ["<tool_call>", "tool_call", '"name":', '"arguments":']
    )

    known_hallucination = "tech solucoes alpha" in _normalize(response)

    return {
        "fact_hits": fact_hits,
        "total_facts": total_facts,
        "faithfulness_score": fact_hits / total_facts if total_facts > 0 else 0.0,
        "hits_detail": hits,
        "tool_call_attempt": tool_call_attempt,
        "known_hallucination": known_hallucination,
    }


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------

def run_v3_benchmark():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d-%H%M")
    summary = []

    engine = AgentRuntime.from_agent_dir(AGENT_DIR)

    print(f"Extraindo conteúdo de: {TEST_DOCUMENT_PATH}")
    extract_result = extract_file_content(TEST_DOCUMENT_PATH)
    if not isinstance(extract_result, dict):
        print("ERRO: extract_file_content não retornou dict.")
        return

    file_text = extract_result.get("text", "")
    extract_method = extract_result.get("method", "unknown")

    if not file_text:
        print("ERRO: extract_file_content retornou texto vazio.")
        return

    print(f"Texto extraído: {len(file_text)} chars via {extract_method}")
    print(f"Primeiros 200 chars:\n{file_text[:200]}\n")

    for scenario, injection_mode, apply_clean, label in CONFIGS_V3:
        print(f"\n[{label}] scenario={scenario}  mode={injection_mode}  clean={apply_clean}")

        history = build_synthetic_history(scenario)

        if apply_clean:
            history_sent = clean_history(history)
        else:
            history_sent = history

        print(f"  turns no history: {len(history)} → enviados: {len(history_sent)}")

        answer = engine._run_with_file_content(
            input_text=PROMPT,
            file_text=file_text,
            mode=injection_mode,
            history=history_sent,
        )

        score = compute_faithfulness_v3(answer, GROUND_TRUTH)

        result = {
            "label": label,
            "scenario": scenario,
            "mode": injection_mode,
            "apply_clean": apply_clean,
            "history_turns_before": len(history),
            "history_turns_sent": len(history_sent),
            "faithfulness_score": score["faithfulness_score"],
            "fact_hits": score["fact_hits"],
            "total_facts": score["total_facts"],
            "hits_detail": score["hits_detail"],
            "tool_call_attempt": score["tool_call_attempt"],
            "known_hallucination": score["known_hallucination"],
            "file_chars": len(file_text),
            "extract_method": extract_method,
            "timestamp": date_str,
            "model": engine.runtime_config.model_default,
            "response_preview": answer[:600],
        }
        summary.append(result)

        run_file = RESULTS_DIR / f"V3-{label}-{date_str}.json"
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(
            f"  faithfulness={score['faithfulness_score']:.2f}  "
            f"hits={score['fact_hits']}/{score['total_facts']}  "
            f"tool_call_attempt={score['tool_call_attempt']}  "
            f"hallucination={score['known_hallucination']}"
        )
        print(f"  preview: {answer[:120]!r}")

    summary_file = RESULTS_DIR / f"V3-summary-{date_str}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nSummary salvo em {summary_file}")
    return summary


if __name__ == "__main__":
    run_v3_benchmark()
