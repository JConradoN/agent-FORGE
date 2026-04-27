#!/usr/bin/env python3
"""
V2 — Document Content Injection Benchmark

Testa diferentes formatos de injeção de conteúdo de documento
para ver quais fazem o gemma4:e4b usar o texto real, em vez
de inventar tool calls ou dados fictícios.

Uso (a partir da raiz do projeto):
    python scripts/run_v2_benchmark.py
"""

import json
from datetime import datetime
from pathlib import Path

from agentforge.runtime.engine import AgentRuntime, _build_input_with_file_content
from agentforge.tools.vault_extract import extract_file_content

AGENT_DIR = "agents/vault-pilot"
RESULTS_DIR = Path("results/benchmarks/V2")

# Documento de teste — contrato real no staging
TEST_DOCUMENT_PATH = (
    "/home/conrado/testes/vault/input/CONRADO/GERAL/Contrato Conrado Nogueira.pdf"
)

# Ground truth — substrings que devem aparecer na resposta se o modelo usar
# o texto real (OCR de tesseract). Valores em minúsculas para matching simples.
# OCR retornou: "CEREJA E OLIVE! A - ME" (artefato de "CEREJA E OLIVEIRA ME"),
# "CNPJ sob 0 n° 37.262.522/0001-71", "Macapa" (de "Macapá"), "Amapa" (de "Amapá").
GROUND_TRUTH = {
    "empresa":   "cereja",          # presente independente do artefato OCR
    "cnpj":      "37.262",          # prefixo robusto do CNPJ real
    "cidade":    "macap",           # cobre "Macapá" e o "Macapa" do OCR
    "tipo":      "prestacao",       # cobre "Prestação" / "prestacao de servico"
}

PROMPT = (
    "Descreva o conteúdo do documento. Inclua: nome das partes, "
    "objeto do contrato, valor (se houver), data e quaisquer outros "
    "dados relevantes presentes no texto."
)

MODES = [
    "current_tag",        # baseline — formato atual com <file_content>
    "tool_response_tag",  # tag <tool_response>
    "plain_block",        # bloco delimitado por ---
    "instruction_strong", # instrução explícita: NÃO chame ferramenta
    "instruction_role",   # instrução de papel: analise sem chamar ferramenta
    "content_last",       # conteúdo depois do input do usuário
    "no_tag",             # sem marcadores, texto direto
]


def compute_faithfulness_v2(response: str, ground_truth: dict) -> dict:
    """
    Verifica quantos fatos do ground truth aparecem na resposta.
    Detecta também se o modelo tentou emitir uma tool_call.
    """
    response_lower = response.lower()
    hits = {}
    for key, value in ground_truth.items():
        hits[key] = value.lower() in response_lower

    fact_hits = sum(hits.values())
    total_facts = len(ground_truth)

    tool_call_attempt = any(
        marker in response_lower
        for marker in ["<tool_call>", "tool_call", '"name":', '"arguments":']
    )

    known_hallucination = "tech soluções alpha" in response_lower

    return {
        "fact_hits": fact_hits,
        "total_facts": total_facts,
        "faithfulness_score": fact_hits / total_facts if total_facts > 0 else 0.0,
        "hits_detail": hits,
        "tool_call_attempt": tool_call_attempt,
        "known_hallucination": known_hallucination,
    }


def run_v2_benchmark():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d-%H%M")
    summary = []

    engine = AgentRuntime.from_agent_dir(AGENT_DIR)

    print(f"Extraindo conteúdo de: {TEST_DOCUMENT_PATH}")
    extract_result = extract_file_content(TEST_DOCUMENT_PATH)
    if not isinstance(extract_result, dict):
        print("ERRO: extract_file_content não retornou um dict.")
        return

    file_text = extract_result.get("text", "")
    extract_method = extract_result.get("method", "unknown")

    if not file_text:
        print("ERRO: extract_file_content retornou texto vazio.")
        return

    print(f"Texto extraído: {len(file_text)} chars via {extract_method}")
    print(f"Primeiros 200 chars:\n{file_text[:200]}\n")

    for mode in MODES:
        print(f"[{mode}] testando...")

        answer = engine._run_with_file_content(
            input_text=PROMPT,
            file_text=file_text,
            mode=mode,
        )

        score = compute_faithfulness_v2(answer, GROUND_TRUTH)

        result = {
            "mode": mode,
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
            "response_preview": answer[:400],
        }
        summary.append(result)

        run_file = RESULTS_DIR / f"V2-{mode}-{date_str}.json"
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(
            f"  faithfulness={score['faithfulness_score']:.2f}  "
            f"hits={score['fact_hits']}/{score['total_facts']}  "
            f"tool_call_attempt={score['tool_call_attempt']}  "
            f"hallucination={score['known_hallucination']}"
        )

    summary_file = RESULTS_DIR / f"V2-summary-{date_str}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nSummary salvo em {summary_file}")
    return summary


if __name__ == "__main__":
    run_v2_benchmark()
