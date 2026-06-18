#!/usr/bin/env python3
"""
Benchmark AgentForge com captura de traces completos para fine-tuning.

DIFERENÇA do run_benchmark_eval.py:
  - Salva o histórico completo de mensagens (system + turns + tool calls + results)
  - Formato JSONL compatível com o dataset de fine-tuning
  - Compara traces do 27b com os sintéticos do Agy

Uso:
    python3 scripts/run_benchmark_capture.py --model qwen3.5:27b --runs 5
    python3 scripts/run_benchmark_capture.py --model qwen3.5:27b --scenarios F3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).parent.parent
AGENTS_DIR   = REPO_ROOT / "agents"
RESULTS_BASE = REPO_ROOT / "benchmark_results"
TRACES_DIR   = REPO_ROOT / "finetune" / "dataset" / "traces_27b"

SCENARIO_MAP = {
    "F3": Path.home() / "repos/estudo/forge/scenarios/F3.json",
    "P3": Path.home() / "repos/estudo/real/scenarios/P3.json",
    "P4": Path.home() / "repos/estudo/real/scenarios/P4.json",
}
AGENT_MAP = {
    "F3": AGENTS_DIR / "forge-f3",
    "P3": AGENTS_DIR / "real-p3",
    "P4": AGENTS_DIR / "real-p4",
}

# ── patch do engine para capturar histórico completo ──────────────────────────

_captured_messages: list[list[dict]] = []
_captured_system: list[str | None] = []


def _patched_run_tool_calling_cycle(self, input_text, system_prompt, history):
    """
    Versão instrumentada de _run_tool_calling_cycle.
    Executa o ciclo normalmente E registra cada mensagem em _captured_messages.
    """
    from agentforge.providers.base import ProviderRequest

    provider = self._get_provider()
    tools_schema = self._build_tools_schema()
    max_cycles = self.runtime_config.max_tool_cycles
    tool_results_log: list[dict] = []

    messages = list(history)
    messages.append({"role": "user", "content": input_text})

    _STUCK_WINDOW = 5
    recent_calls: list[str] = []
    _MAX_TOOL_REDIRECTS = 2
    no_tool_redirects = 0

    for cycle in range(max_cycles):
        request = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text="" if cycle > 0 else input_text,
            system_prompt=system_prompt,
            model=self.runtime_config.model_default,
            history=messages[:-1] if cycle == 0 else messages,
            tools_schema=tools_schema if tools_schema else None,
        )
        response = provider.generate(request)

        if not response.tool_calls:
            if (
                tools_schema
                and not tool_results_log
                and no_tool_redirects < _MAX_TOOL_REDIRECTS
            ):
                no_tool_redirects += 1
                messages.append({"role": "assistant", "content": response.output_text})
                messages.append({
                    "role": "user",
                    "content": (
                        "You have not used any tools yet. "
                        "Do NOT output code or text directly — use the available tools to complete the task. "
                        "Call the appropriate tool now to proceed."
                    ),
                })
                continue
            # Captura o histórico final antes de retornar
            _captured_messages.append(list(messages) + [
                {"role": "assistant", "content": response.output_text}
            ])
            _captured_system.append(system_prompt)
            return response.output_text, tool_results_log

        messages.append({
            "role": "assistant",
            "content": response.output_text or "",
            "tool_calls": [
                {"function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in response.tool_calls
            ],
        })

        loop_detected = False
        for tc in response.tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("arguments") or {}
            call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"

            result = self._execute_tool(tool_name, **tool_args)
            tool_results_log.append({
                "tool": tool_name, "args": tool_args,
                "result": result, "cycle": cycle,
            })
            result_text = json.dumps(result, ensure_ascii=False, default=str) if result else "null"
            messages.append({"role": "tool", "content": result_text, "name": tool_name})

            call_result_key = f"{call_key}::{result_text}"
            recent_calls.append(call_result_key)
            if len(recent_calls) > _STUCK_WINDOW:
                recent_calls.pop(0)
            if len(recent_calls) == _STUCK_WINDOW and len(set(recent_calls)) == 1:
                loop_detected = True
                break

        if loop_detected:
            break

    # Completion hint (igual ao engine original)
    import re as _re
    must_rules = self.agent_spec.guardrails.must
    exec_lines = [
        f"  - {e['tool']}({json.dumps(e.get('args', {}), ensure_ascii=False)[:80]})"
        for e in tool_results_log
    ]
    exec_summary = "Tools already executed:\n" + "\n".join(exec_lines) if exec_lines else "No tools were executed."
    completion_hint = f"Produce your final response based on the tools executed above.\n\n{exec_summary}"
    if must_rules:
        phrases = []
        for rule in must_rules:
            quoted = _re.findall(r"'([^']+)'", rule)
            phrases.extend(quoted)
        if phrases:
            completion_hint += "\n\nYour response MUST include: " + ", ".join(f"'{p}'" for p in phrases[:3])

    messages.append({"role": "user", "content": completion_hint})

    final_req = ProviderRequest(
        agent_id=self.runtime_config.agent_id,
        input_text="",
        system_prompt=system_prompt,
        model=self.runtime_config.model_default,
        history=messages,
    )
    final_response = provider.generate(final_req)
    messages.append({"role": "assistant", "content": final_response.output_text})

    # Captura histórico completo
    _captured_messages.append(list(messages))
    _captured_system.append(system_prompt)

    return final_response.output_text, tool_results_log


# ── runner + scorer (reutilizado do original) ─────────────────────────────────

def _score(checks, workdir, output, tool_calls_log, model_slug=""):
    """Versão simplificada do scorer — só importa o score final aqui."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    # Importa funções do script original
    import run_benchmark_eval as orig
    return orig.score_auto_checks(checks, workdir, output, tool_calls_log, model_slug)


def run_and_capture(scenario_id: str, model: str, run_index: int) -> dict:
    global _captured_messages, _captured_system
    _captured_messages = []
    _captured_system = []

    scenario_path = SCENARIO_MAP[scenario_id]
    agent_dir = AGENT_MAP[scenario_id]
    scenario = json.loads(scenario_path.read_text())
    prompt = scenario["prompt"]
    model_slug = model.replace(":", "-").replace("/", "_")
    prompt = prompt.replace("{model_slug}", model_slug)
    checks = scenario.get("auto_checks", [])

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    workdir = RESULTS_BASE / scenario_id / model_slug / f"capture_{run_ts}"
    workdir.mkdir(parents=True, exist_ok=True)
    os.environ["AGENT_WORKDIR"] = str(workdir)
    os.environ["AGENTFORGE_MODEL_OVERRIDE"] = model

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from agentforge.runtime.engine import AgentRuntime
    import types

    # Monkey-patch para capturar histórico
    AgentRuntime._run_tool_calling_cycle = _patched_run_tool_calling_cycle

    t0 = time.perf_counter()
    try:
        runtime = AgentRuntime.from_agent_dir(str(agent_dir))
        runtime.runtime_config.model_default = model
        result = runtime.run(prompt)
    except Exception as e:
        return {"error": str(e), "score": 0, "max_score": sum(c.get("weight", 1) for c in checks), "messages": []}

    latency_ms = round((time.perf_counter() - t0) * 1000)
    output = result.get("output", "")
    tool_calls_log = result.get("metadata", {}).get("tool_calls_log") or []

    score, max_score, details = _score(checks, workdir, output, tool_calls_log, model_slug)
    pct = round(score / max_score * 100, 1) if max_score else 0.0

    # Monta o exemplo de treinamento a partir das mensagens capturadas
    system_prompt = _captured_system[0] if _captured_system else None
    raw_messages = _captured_messages[0] if _captured_messages else []

    # Normaliza para o formato do dataset
    training_messages = []
    if system_prompt:
        training_messages.append({"role": "system", "content": system_prompt})
    for m in raw_messages:
        training_messages.append(m)

    return {
        "id": f"trace-27b-{scenario_id}-run{run_index}",
        "source": "trace_27b",
        "category": "agentforge",
        "subcategory": scenario_id.lower(),
        "model": model,
        "score": score,
        "max_score": max_score,
        "pct": pct,
        "latency_ms": latency_ms,
        "messages": training_messages,
        "tool_calls_log": tool_calls_log,
        "details": details,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Captura traces completos para fine-tuning")
    parser.add_argument("--scenarios", nargs="+", default=["F3", "P3", "P4"],
                        choices=list(SCENARIO_MAP.keys()))
    parser.add_argument("--model", default="qwen3.5:27b")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--min-score-pct", type=float, default=70.0,
                        help="Só salva como gold se score >= N%% (default: 70)")
    args = parser.parse_args()

    TRACES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nAgentForge Trace Capture — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Modelo: {args.model}  |  Cenários: {args.scenarios}  |  Runs: {args.runs}")
    print(f"Gold threshold: >={args.min_score_pct}%")
    print("=" * 60)

    all_examples = []
    gold_examples = []

    for sid in args.scenarios:
        print(f"\n[{sid}] Capturando {args.runs} runs...")
        for i in range(1, args.runs + 1):
            print(f"  run {i}/{args.runs}... ", end="", flush=True)
            ex = run_and_capture(sid, args.model, i)
            if "error" in ex:
                print(f"ERRO: {ex['error']}")
                continue

            flag = "GOLD" if ex["pct"] >= args.min_score_pct else "skip"
            print(f"{ex['score']}/{ex['max_score']} ({ex['pct']}%) [{flag}]  turns={len(ex['messages'])}")

            all_examples.append(ex)
            if ex["pct"] >= args.min_score_pct:
                gold_examples.append(ex)

            # Aguarda entre runs para evitar contaminação de VRAM
            if i < args.runs:
                time.sleep(5)

    # Salva todos
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_path = TRACES_DIR / f"traces_all_{ts}.jsonl"
    gold_path = TRACES_DIR / f"traces_gold_{ts}.jsonl"

    with open(all_path, "w") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False, default=str) + "\n")

    with open(gold_path, "w") as f:
        for ex in gold_examples:
            entry = {
                "id": ex["id"],
                "source": ex["source"],
                "category": ex["category"],
                "subcategory": ex["subcategory"],
                "messages": ex["messages"],
                "score_pct": ex["pct"],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Relatório de checks falhos para orientar ajustes sintéticos
    print("\nDetalhes dos checks falhos (para orientar o Agy):")
    for ex in all_examples:
        for detail in ex.get("details", []):
            if not detail.get("passed"):
                print(f"  [{ex['id']}] FALHOU: {detail.get('label','?')}")

    print(f"\n{'='*60}")
    print(f"  Total runs: {len(all_examples)}")
    print(f"  Gold (>={args.min_score_pct}%): {len(gold_examples)}")
    print(f"  Todos:  {all_path}")
    print(f"  Gold:   {gold_path}")


if __name__ == "__main__":
    main()
