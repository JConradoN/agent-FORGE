#!/usr/bin/env python3
"""
V4 — Hallucinated Summary + Error Loop Benchmark

Reproduz o Bug A:
  - Resumo de sistema alucinado (lista de arquivos inventados) é injetado
    como turn role:"system" no histórico.
  - Loops de "arquivo não encontrado" acumulam turns assistant:"" no contexto.
  - O modelo ignora o <file_content> real injetado e repete erros.

Testa se instruction_strong e/ou truncação do histórico mitiga o bug.

Uso (a partir da raiz do projeto):
    python scripts/run_v4_benchmark_summary.py
"""

import json
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path

from agentforge.runtime.engine import AgentRuntime
from agentforge.tools.vault_extract import extract_file_content

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

AGENT_DIR = "agents/vault-pilot"
RESULTS_DIR = Path("results/benchmarks/V4")
HISTORY_PATH = Path(AGENT_DIR) / "history.json"

TEST_DOCUMENT_PATH = (
    "/home/conrado/testes/vault/input/CONRADO/GERAL/Contrato Conrado Nogueira.pdf"
)

GROUND_TRUTH = {
    "empresa": "CEREJA",
    "cnpj": "37.262",
    "cidade": "Macapá",
    "tipo": "prestação de serviços",
}

PROMPT = (
    "Descreva o conteúdo do documento. Inclua: nome das partes, "
    "objeto do contrato, valor (se houver), data e quaisquer outros "
    "dados relevantes presentes no texto."
)

# Resumo alucinado real (gerado pelo modelo em sessão anterior; 24 arquivos, nenhum real)
_HARDCODED_SUMMARY = (
    "Resumo da conversa anterior:\n"
    "- Usuário: Liste os arquivos no staging e me devolva o resultado agrupado por pasta.\n"
    "- Assistente: Os arquivos disponíveis, agrupados por pasta, são: "
    " **EMILIA/JURIDICO/**"
    " *   EMILIA/JURIDICO/EMILIA.pdf"
    " **EMILIA/DOCUMENTOS/**"
    " *   EMILIA/DOCUMENTOS/EMILIA_documentos.pdf"
    " **EMILIA/HABITACIONAL/**"
    " *   EMILIA/HABITACIONAL/COMPROVANTE_RESIDENCIA.pdf"
    " **EMILIA/SAUDE/**"
    " *   EMILIA/SAUDE/EXAME_BLOOD.pdf"
    " **EMILIA/CURRICULO/**"
    " *   EMILIA/CURRICULO/Curriculo_Emilia.pdf"
    " **EMILIA/TRABALHO/**"
    " *   EMILIA/TRABALHO/Carteira_Trabalho_Emilia.pdf"
    " **EMILIA/JURIDICO/**"
    " *   EMILIA/JURIDICO/RG.pdf"
    " *   EMILIA/JURIDICO/CPF.pdf"
    " **EMILIA/JURIDICO/**"
    " *   EMILIA/JURIDICO/Certidao_Nascimento.pdf"
    " **EMILIA/JURIDICO/**"
    " *   EMILIA/JURIDICO/CNH.pdf"
    " **CONRADO/JURIDICO/**"
    " *   CONRADO/JURIDICO/Contrato_Conrado.pdf"
    " **CONRADO/DOCUMENTOS/**"
    " *   CONRADO/DOCUMENTOS/CONRADO_documentos.pdf"
    " **CONRADO/HABITACIONAL/**"
    " *   CONRADO/HABITACIONAL/COMPROVANTE_RESIDENCIA_CONRADO.pdf"
    " **CONRADO/SAUDE/**"
    " *   CONRADO/SAUDE/EXAME_BLOOD_CONRADO.pdf"
    " **CONRADO/CURRICULO/**"
    " *   CONRADO/CURRICULO/Curriculo_Conrado.pdf"
    " **CONRADO/TRABALHO/**"
    " *   CONRADO/TRABALHO/Carteira_Trabalho_Conrado.pdf"
    " **CONRADO/JURIDICO/**"
    " *   CONRADO/JURIDICO/RG_Conrado.pdf"
    " *   CONRADO/JURIDICO/CPF_Conrado.pdf"
    " **CONRADO/JURIDICO/**"
    " *   CONRADO/JURIDICO/Certidao_Nascimento_Conrado.pdf"
    " **CONRADO/JURIDICO/**"
    " *   CONRADO/JURIDICO/CNH_Conrado.pdf"
    " [24 arquivos no total, nenhum real]"
)

# (scenario, mode, apply_trunc, label)
CONFIGS_V4 = [
    ("summary_only",  "current_tag",        False, "sum_only__current__raw"),
    ("summary_only",  "current_tag",        True,  "sum_only__current__trunc"),
    ("summary_only",  "instruction_strong", False, "sum_only__strong__raw"),
    ("summary_only",  "instruction_strong", True,  "sum_only__strong__trunc"),
    ("summary_loops", "current_tag",        False, "sum_loops__current__raw"),
    ("summary_loops", "current_tag",        True,  "sum_loops__current__trunc"),
    ("summary_loops", "instruction_strong", False, "sum_loops__strong__raw"),
    ("summary_loops", "instruction_strong", True,  "sum_loops__strong__trunc"),
]


# ---------------------------------------------------------------------------
# Carregamento do resumo alucinado
# ---------------------------------------------------------------------------

def load_hallucinated_summary() -> str:
    """
    Tenta recuperar o turn role:system com o resumo alucinado real de history.json
    ou do commit 530d197 via git show.
    Usa o hardcoded fallback se nenhum dos dois estiver disponível.
    """
    # 1. Tenta history.json atual
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            for turn in history:
                if turn.get("role") == "system" and "Resumo" in turn.get("content", ""):
                    return turn["content"]
        except (json.JSONDecodeError, KeyError):
            pass

    # 2. Tenta recuperar do commit git onde o bug foi observado
    try:
        result = subprocess.run(
            ["git", "show", "530d197:agents/vault-pilot/history.json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            history = json.loads(result.stdout)
            for turn in history:
                if turn.get("role") == "system" and "Resumo" in turn.get("content", ""):
                    return turn["content"]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass

    # 3. Fallback: resumo alucinado hardcoded (texto real da sessão original)
    return _HARDCODED_SUMMARY


# ---------------------------------------------------------------------------
# Construção do histórico sintético
# ---------------------------------------------------------------------------

def build_v4_history(scenario: str, summary_text: str) -> list[dict]:
    """
    scenario:
      "summary_only"  — apenas o turn system com o resumo alucinado
      "summary_loops" — resumo + 3 ciclos de "arquivo não encontrado"
    """
    def turn(role: str, content: str) -> dict:
        return {"role": role, "content": content}

    if scenario == "summary_only":
        return [
            turn("system", summary_text),
        ]

    if scenario == "summary_loops":
        return [
            turn("system", summary_text),
            turn("user",      "Extraia o arquivo CONRADO/GERAL/Contrato Conrado Nogueira.pdf"),
            turn("assistant", ""),
            turn("user",      "O arquivo não foi encontrado. Tente novamente."),
            turn("assistant", ""),
            turn("user",      "O arquivo CONRADO/GERAL/Contrato Conrado Nogueira.pdf ainda não foi localizado."),
            turn("assistant", ""),
        ]

    return []


def truncate_history(history: list[dict], max_turns: int = 8) -> list[dict]:
    return history[-max_turns:]


# ---------------------------------------------------------------------------
# Métricas V4 estendidas
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def compute_v4_metrics(response: str, ground_truth: dict) -> dict:
    response_norm = _normalize(response)

    hits = {key: _normalize(value) in response_norm for key, value in ground_truth.items()}
    fact_hits = sum(hits.values())
    total_facts = len(ground_truth)

    tool_call_markup = any(
        marker in response.lower()
        for marker in ["<tool_call>", "tool_call", '"name":', '"arguments":']
    )

    hallucination_detected = (
        "emilia" in response_norm
        or "tech solucoes alpha" in response_norm
        or "curriculo_emilia" in response_norm
    )

    waiting_pattern = any(
        phrase in response_norm
        for phrase in [
            "arquivo nao encontrado",
            "nao foi encontrado",
            "nao foi localizado",
            "arquivo nao localizado",
            "nao consigo encontrar",
        ]
    )

    faithfulness_score = fact_hits / total_facts if total_facts > 0 else 0.0

    bug_reproduced = (
        tool_call_markup
        or waiting_pattern
        or (faithfulness_score < 0.5 and hallucination_detected)
    )

    return {
        "fact_hits": fact_hits,
        "total_facts": total_facts,
        "faithfulness_score": faithfulness_score,
        "hits_detail": hits,
        "tool_call_markup": tool_call_markup,
        "hallucination_detected": hallucination_detected,
        "waiting_pattern": waiting_pattern,
        "bug_reproduced": bug_reproduced,
    }


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------

def run_v4_benchmark_summary():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d-%H%M")
    summary = []

    summary_text = load_hallucinated_summary()
    print(f"Resumo alucinado carregado: {len(summary_text)} chars")
    print(f"Primeiros 150 chars: {summary_text[:150]!r}\n")

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

    for scenario, mode, apply_trunc, label in CONFIGS_V4:
        print(f"\n[{label}]  scenario={scenario}  mode={mode}  trunc={apply_trunc}")

        history_raw = build_v4_history(scenario, summary_text)
        history_sent = truncate_history(history_raw) if apply_trunc else history_raw

        print(f"  turns no history: {len(history_raw)} → enviados: {len(history_sent)}")

        answer = engine._run_with_file_content(
            input_text=PROMPT,
            file_text=file_text,
            mode=mode,
            history=history_sent,
        )

        metrics = compute_v4_metrics(answer, GROUND_TRUTH)

        result = {
            "label": label,
            "scenario": scenario,
            "mode": mode,
            "apply_trunc": apply_trunc,
            "history_turns_raw": len(history_raw),
            "history_turns_sent": len(history_sent),
            "faithfulness_score": metrics["faithfulness_score"],
            "fact_hits": metrics["fact_hits"],
            "total_facts": metrics["total_facts"],
            "hits_detail": metrics["hits_detail"],
            "tool_call_markup": metrics["tool_call_markup"],
            "hallucination_detected": metrics["hallucination_detected"],
            "waiting_pattern": metrics["waiting_pattern"],
            "bug_reproduced": metrics["bug_reproduced"],
            "file_chars": len(file_text),
            "extract_method": extract_method,
            "timestamp": date_str,
            "model": engine.runtime_config.model_default,
            "response_preview": answer[:600],
        }
        summary.append(result)

        run_file = RESULTS_DIR / f"V4-{label}-{date_str}.json"
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        bug_flag = "BUG" if metrics["bug_reproduced"] else "OK "
        print(
            f"  [{bug_flag}] faithfulness={metrics['faithfulness_score']:.2f}  "
            f"hits={metrics['fact_hits']}/{metrics['total_facts']}  "
            f"tool_call={metrics['tool_call_markup']}  "
            f"hallucination={metrics['hallucination_detected']}  "
            f"waiting={metrics['waiting_pattern']}"
        )
        print(f"  preview: {answer[:150]!r}")

    summary_file = RESULTS_DIR / f"V4-summary-{date_str}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*72}")
    print(f"{'label':<35} {'faith':>5}  {'bug':>5}  {'tool':>5}  {'hall':>5}  {'wait':>5}")
    print(f"{'-'*72}")
    for r in summary:
        print(
            f"{r['label']:<35} "
            f"{r['faithfulness_score']:>5.2f}  "
            f"{'YES' if r['bug_reproduced'] else 'no ':>5}  "
            f"{'YES' if r['tool_call_markup'] else 'no ':>5}  "
            f"{'YES' if r['hallucination_detected'] else 'no ':>5}  "
            f"{'YES' if r['waiting_pattern'] else 'no ':>5}"
        )
    print(f"{'='*72}")
    print(f"\nSummary salvo em {summary_file}")
    return summary


if __name__ == "__main__":
    run_v4_benchmark_summary()
