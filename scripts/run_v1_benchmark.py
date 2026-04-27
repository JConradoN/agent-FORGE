#!/usr/bin/env python3
"""
V1 — Tool Output Faithfulness Benchmark

Testa se o problema de o modelo ignorar o tool output de scan_directory
é causado por VOLUME ou por FORMATO do JSON injetado no prompt.

Uso (a partir da raiz do projeto):
    python scripts/run_v1_benchmark.py
"""

import json
import re
from datetime import datetime
from pathlib import Path

from agentforge.runtime.engine import AgentRuntime, _summarize_scan_output
from agentforge.tools.vault_scan import scan_directory

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
STAGING_PATH = "/home/conrado/testes/vault/input"
AGENT_DIR = str(REPO_ROOT / "agents/vault-pilot")
RESULTS_DIR = REPO_ROOT / "results/benchmarks/V1"
PROMPT = "Liste os arquivos encontrados no diretório de staging."

# (n_files, mode, label)
# n_files=None significa "todos" (baseline completo)
CONFIGS = [
    (5,    "full",       "n5_full"),
    (20,   "full",       "n20_full"),
    (50,   "full",       "n50_full"),
    (None, "full",       "n342_full"),      # baseline atual — deve falhar
    (None, "top_n",      "n342_top20"),
    (None, "summary",    "n342_summary"),
    (None, "by_folder",  "n342_by_folder"),
    (None, "plain_text", "n342_plain"),
]

# ---------------------------------------------------------------------------
# Faithfulness
# ---------------------------------------------------------------------------

FILE_REGEX = re.compile(
    r"[A-Za-z0-9_\-/.]+\.(pdf|docx?|jpg|jpeg|png|xlsx?|txt)",
    re.IGNORECASE,
)


def compute_faithfulness(response_text: str, real_paths: list[str]) -> dict:
    """
    Extrai nomes de arquivo da resposta do modelo e compara com a lista real.
    """
    mentioned = {m.group(0) for m in FILE_REGEX.finditer(response_text)}
    real_set = set(real_paths)

    correct = {m for m in mentioned if any(m in r for r in real_set)}
    invented = mentioned - correct

    mentioned_count = len(mentioned)
    correct_count = len(correct)

    return {
        "mentioned": mentioned_count,
        "correct": correct_count,
        "invented": len(invented),
        "faithfulness_score": correct_count / mentioned_count if mentioned_count > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def run_v1_benchmark():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d-%H%M")
    summary = []

    engine = AgentRuntime.from_agent_dir(AGENT_DIR)
    model_name = engine.runtime_config.model_default

    # Scan completo uma única vez
    full_tool_data = scan_directory(directory=STAGING_PATH)
    all_files = full_tool_data.get("files", [])
    total_real = full_tool_data.get("file_count", len(all_files))
    print(f"scan_directory: {total_real} arquivos encontrados em {STAGING_PATH}\n")

    for n_files, fmt, label in CONFIGS:
        print(f"[{label}] N={n_files or total_real}, formato={fmt}")

        # Montar tool_data com slice de n_files (None = todos)
        if n_files is not None and n_files < total_real:
            sliced_files = all_files[:n_files]
            tool_data = {
                "directory": full_tool_data["directory"],
                "file_count": n_files,
                "files": sliced_files,
            }
        else:
            tool_data = full_tool_data

        # Lista real para faithfulness
        real_paths = [f["path"] for f in tool_data.get("files", [])]

        # Formatar conforme o modo do experimento
        formatted = _summarize_scan_output(tool_data, mode=fmt, max_items=20)

        # Estimar tokens do tool output formatado
        formatted_str = formatted.get("_text", json.dumps(formatted, ensure_ascii=False))
        tokens_estimated = len(formatted_str) // 4

        # Chamar o modelo com tool output pré-formatado (bypassa intent detection)
        answer = engine._run_with_tool_data(
            input_text=PROMPT,
            tool_data=formatted,
        )

        # Calcular faithfulness
        score = compute_faithfulness(answer, real_paths)

        result = {
            "config": {"n": n_files or total_real, "mode": fmt, "label": label},
            "tokens_estimated": tokens_estimated,
            "mentioned": score["mentioned"],
            "correct": score["correct"],
            "invented": score["invented"],
            "faithfulness_score": score["faithfulness_score"],
            "timestamp": date_str,
            "model": model_name,
            "response_preview": answer[:300],
        }
        summary.append(result)

        run_file = RESULTS_DIR / f"V1-{label}-{date_str}.json"
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(
            f"  faithfulness={score['faithfulness_score']:.2f}  "
            f"tokens~{tokens_estimated}  "
            f"mentioned={score['mentioned']}  "
            f"correct={score['correct']}  "
            f"invented={score['invented']}"
        )

    summary_file = RESULTS_DIR / f"V1-summary-{date_str}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nSummary salvo em {summary_file}")
    return summary


if __name__ == "__main__":
    run_v1_benchmark()
