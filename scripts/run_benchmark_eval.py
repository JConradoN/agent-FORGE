#!/usr/bin/env python3
"""
Benchmark AgentForge — roda agentes nos cenários FORGE F3, REAL P3 e REAL P4.

Avalia usando auto_checks do cenário, registra scores e envia resultado via Claudio.

Uso:
    python3 scripts/run_benchmark_eval.py
    python3 scripts/run_benchmark_eval.py --scenarios F3 P3
    python3 scripts/run_benchmark_eval.py --model qwen3.5:9b
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── caminhos ──────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.parent
AGENTS_DIR   = REPO_ROOT / "agents"
RESULTS_BASE = REPO_ROOT / "benchmark_results"
FORGE_DIR    = Path.home() / "repos/estudo/forge"
REAL_DIR     = Path.home() / "repos/estudo/real"

SCENARIO_MAP = {
    "F3": FORGE_DIR / "scenarios" / "F3.json",
    "P3": REAL_DIR  / "scenarios" / "P3.json",
    "P4": REAL_DIR  / "scenarios" / "P4.json",
}

AGENT_MAP = {
    "F3": AGENTS_DIR / "forge-f3",
    "P3": AGENTS_DIR / "real-p3",
    "P4": AGENTS_DIR / "real-p4",
}

DEFAULT_SCENARIOS = ["F3", "P3", "P4"]


# ── auto_check evaluation ──────────────────────────────────────────────────────

def check_file_exists(workdir: Path, check: dict) -> tuple[bool, str]:
    path = check["path"]
    ok = (workdir / path).exists()
    return ok, f"{'OK' if ok else 'FALTA'} — {path}"


def check_file_contains(workdir: Path, check: dict) -> tuple[bool, str]:
    path  = check["path"]
    needle = check["needle"]
    target = workdir / path
    if not target.exists():
        return False, f"arquivo não encontrado: {path}"
    ok = needle.lower() in target.read_text(errors="replace").lower()
    return ok, f"{'OK' if ok else 'FALTA needle'} '{needle}' em {path}"


def check_json_valid(workdir: Path, check: dict) -> tuple[bool, str]:
    path   = check["path"]
    target = workdir / path
    if not target.exists():
        return False, f"arquivo não encontrado: {path}"
    try:
        data = json.loads(target.read_text())
        min_items = check.get("min_items", 0)
        if min_items and isinstance(data, list) and len(data) < min_items:
            return False, f"JSON tem {len(data)} itens, mínimo {min_items}"
        return True, f"JSON válido ({len(data) if isinstance(data, list) else 'objeto'})"
    except Exception as e:
        return False, f"JSON inválido: {e}"


def check_json_has_keys(workdir: Path, check: dict) -> tuple[bool, str]:
    path   = check["path"]
    keys   = check["keys"]
    target = workdir / path
    if not target.exists():
        return False, f"arquivo não encontrado: {path}"
    try:
        data = json.loads(target.read_text())
        if isinstance(data, list) and data:
            item = data[0]
        elif isinstance(data, dict):
            item = data
        else:
            return False, "JSON não é objeto nem lista"
        missing = [k for k in keys if k not in item]
        if missing:
            return False, f"campos faltando: {missing}"
        return True, f"campos OK: {keys}"
    except Exception as e:
        return False, f"erro ao ler JSON: {e}"


def check_python_syntax(workdir: Path, check: dict) -> tuple[bool, str]:
    path   = check["path"]
    target = workdir / path
    if not target.exists():
        return False, f"arquivo não encontrado: {path}"
    try:
        compile(target.read_text(), str(target), "exec")
        return True, "sintaxe Python válida"
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"


def check_python_tests_pass(workdir: Path, check: dict) -> tuple[bool, str]:
    test_file = check["test_file"]
    target    = workdir / test_file
    if not target.exists():
        return False, f"arquivo de teste não encontrado: {test_file}"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        ok = proc.returncode == 0
        # extrai linha de sumário ex: "5 passed, 0 failed"
        summary_lines = [l for l in proc.stdout.splitlines() if "passed" in l or "failed" in l or "error" in l]
        summary = summary_lines[-1].strip() if summary_lines else proc.stdout[-200:]
        return ok, summary
    except Exception as e:
        return False, f"erro ao rodar pytest: {e}"


def check_skill_has_frontmatter(workdir: Path, check: dict) -> tuple[bool, str]:
    path   = check["path"]
    target = workdir / path
    if not target.exists():
        return False, f"arquivo não encontrado: {path}"
    text = target.read_text(errors="replace")
    ok = text.startswith("---") and "---" in text[3:]
    return ok, f"{'frontmatter OK' if ok else 'frontmatter ausente ou inválido'}"


def check_skill_has_sections(workdir: Path, check: dict) -> tuple[bool, str]:
    path     = check["path"]
    sections = check.get("sections", [])
    target   = workdir / path
    if not target.exists():
        return False, f"arquivo não encontrado: {path}"
    text_lower = target.read_text(errors="replace").lower()
    missing = [s for s in sections if s.lower() not in text_lower]
    if missing:
        return False, f"seções faltando: {missing}"
    return True, f"todas as seções presentes: {sections}"


def check_response_contains(output: str, check: dict) -> tuple[bool, str]:
    needle = check["needle"]
    ok     = needle.lower() in output.lower()
    return ok, f"{'OK' if ok else 'FALTA'} '{needle}' na resposta"


def check_tool_called(tool_calls_log: list[dict], check: dict) -> tuple[bool, str]:
    tool = check["tool"]
    ok   = any(t.get("tool") == tool for t in (tool_calls_log or []))
    return ok, f"tool '{tool}' {'chamada' if ok else 'NÃO chamada'}"


def check_tool_call_url_contains(tool_calls_log: list[dict], check: dict) -> tuple[bool, str]:
    tool    = check.get("tool", "http_get")
    pattern = check.get("url_needle", "")
    for tc in (tool_calls_log or []):
        if tc.get("tool") == tool:
            url = tc.get("args", {}).get("url", "")
            if pattern.lower() in url.lower():
                return True, f"OK → URL contém '{pattern}'"
    return False, f"NÃO encontrado: tool '{tool}' com URL contendo '{pattern}'"


def check_tool_call_result_contains(tool_calls_log: list[dict], check: dict) -> tuple[bool, str]:
    tool       = check.get("tool", "http_get")
    url_pat    = check.get("url_needle", "")
    result_pat = check.get("result_needle", "")
    for tc in (tool_calls_log or []):
        if tc.get("tool") != tool:
            continue
        url = tc.get("args", {}).get("url", "")
        if url_pat and url_pat.lower() not in url.lower():
            continue
        result_text = str(tc.get("result", ""))
        if result_pat.lower() in result_text.lower():
            return True, f"OK → resultado contém '{result_pat}'"
    return False, f"NÃO encontrado: tool '{tool}' URL~'{url_pat}' com resultado~'{result_pat}'"


def check_no_error(output: str, _check: dict) -> tuple[bool, str]:
    err_patterns = ["[ERRO]", "Error:", "Traceback", "Exception:"]
    for pat in err_patterns:
        if pat in output:
            return False, f"erro encontrado: {pat}"
    return True, "sem erros detectados"


def score_auto_checks(
    checks: list[dict],
    workdir: Path,
    output: str,
    tool_calls_log: list[dict],
    model_slug: str = "",
) -> tuple[int, int, list[dict]]:
    """Retorna (score, max_score, detalhes)."""
    total  = 0
    earned = 0
    details = []

    for check in checks:
        # substitui {model_slug} nos path/needle templates
        check = {
            k: (v.replace("{model_slug}", model_slug) if isinstance(v, str) else v)
            for k, v in check.items()
        }

        ctype  = check["type"]
        weight = check.get("weight", 1)
        label  = check.get("label", ctype)
        total += weight

        try:
            if ctype == "file_exists":
                ok, detail = check_file_exists(workdir, check)
            elif ctype == "file_contains":
                ok, detail = check_file_contains(workdir, check)
            elif ctype == "json_valid":
                ok, detail = check_json_valid(workdir, check)
            elif ctype == "json_has_keys":
                ok, detail = check_json_has_keys(workdir, check)
            elif ctype == "python_syntax":
                ok, detail = check_python_syntax(workdir, check)
            elif ctype == "python_tests_pass":
                ok, detail = check_python_tests_pass(workdir, check)
            elif ctype == "skill_has_frontmatter":
                ok, detail = check_skill_has_frontmatter(workdir, check)
            elif ctype == "skill_has_sections":
                ok, detail = check_skill_has_sections(workdir, check)
            elif ctype == "response_contains":
                ok, detail = check_response_contains(output, check)
            elif ctype == "tool_called":
                ok, detail = check_tool_called(tool_calls_log, check)
            elif ctype == "tool_call_url_contains":
                ok, detail = check_tool_call_url_contains(tool_calls_log, check)
            elif ctype == "tool_call_result_contains":
                ok, detail = check_tool_call_result_contains(tool_calls_log, check)
            elif ctype == "no_error":
                ok, detail = check_no_error(output, check)
            else:
                ok, detail = False, f"check type '{ctype}' não implementado"
        except Exception as e:
            ok, detail = False, f"exceção ao avaliar: {e}"

        if ok:
            earned += weight

        details.append({
            "label": label,
            "type":  ctype,
            "ok":    ok,
            "weight": weight,
            "detail": detail,
        })

    return earned, total, details


# ── runner ────────────────────────────────────────────────────────────────────

def run_agent_on_scenario(scenario_id: str, model: str) -> dict:
    """Roda agent AgentForge no cenário e retorna {score, max_score, details, output, latency_ms}."""
    scenario_path = SCENARIO_MAP[scenario_id]
    agent_dir     = AGENT_MAP[scenario_id]

    scenario = json.loads(scenario_path.read_text())
    prompt   = scenario["prompt"]
    model_slug = model.replace(":", "-").replace("/", "_")

    # Substituições de template no prompt (ex: {model_slug})
    prompt = prompt.replace("{model_slug}", model_slug)
    # F3 usa {model_slug} no nome do arquivo — também nos auto_checks
    checks = scenario.get("auto_checks", [])

    workdir = RESULTS_BASE / scenario_id / model_slug
    workdir.mkdir(parents=True, exist_ok=True)

    # Define workdir para os tools via env var
    os.environ["AGENT_WORKDIR"] = str(workdir)

    # Sobrescreve o modelo padrão do agent
    # AgentRuntime respeita model_policy.default_model do YAML
    # Aqui passamos por variável de ambiente para override
    os.environ["AGENTFORGE_MODEL_OVERRIDE"] = model

    # Importa após setar env
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from agentforge.runtime.engine import AgentRuntime  # noqa: E402

    t0 = time.perf_counter()
    try:
        runtime = AgentRuntime.from_agent_dir(str(agent_dir))
        # Sobrescreve modelo se diferente
        if model and runtime.runtime_config.model_default != model:
            runtime.runtime_config.model_default = model
        result = runtime.run(prompt)
    except Exception as e:
        return {
            "scenario": scenario_id,
            "model": model,
            "error": str(e),
            "score": 0,
            "max_score": sum(c.get("weight", 1) for c in checks),
            "pct": 0.0,
            "details": [],
            "output": "",
            "latency_ms": round((time.perf_counter() - t0) * 1000),
        }

    latency_ms = round((time.perf_counter() - t0) * 1000)
    output         = result.get("output", "")
    tool_calls_log = result.get("metadata", {}).get("tool_calls_log") or []

    score, max_score, details = score_auto_checks(
        checks, workdir, output, tool_calls_log, model_slug=model_slug
    )
    pct = round(score / max_score * 100, 1) if max_score else 0.0

    # Salva resultado JSON
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = workdir / f"agentforge_{scenario_id}_{model_slug}_{ts}.json"
    result_file.write_text(json.dumps({
        "scenario": scenario_id,
        "model": model,
        "score": score,
        "max_score": max_score,
        "pct": pct,
        "latency_ms": latency_ms,
        "output": output[:2000],
        "tool_calls_log": tool_calls_log,
        "details": details,
    }, ensure_ascii=False, indent=2))

    return {
        "scenario": scenario_id,
        "model": model,
        "score": score,
        "max_score": max_score,
        "pct": pct,
        "latency_ms": latency_ms,
        "details": details,
        "output": output,
    }


# ── formatação ────────────────────────────────────────────────────────────────

def format_scenario_report(r: dict) -> str:
    lines = [
        f"\n{'='*60}",
        f"  {r['scenario']} | {r['model']}",
        f"  Score: {r['score']}/{r['max_score']} ({r['pct']}%)  |  {r['latency_ms']/1000:.1f}s",
        f"{'='*60}",
    ]
    if r.get("error"):
        lines.append(f"  ERRO: {r['error']}")
    else:
        for d in r.get("details", []):
            status = "✓" if d["ok"] else "✗"
            lines.append(f"  [{status}] {d['label']} (w={d['weight']}): {d['detail']}")
    return "\n".join(lines)


def build_telegram_summary(results: list[dict]) -> str:
    lines = ["*AgentForge — Benchmark FORGE/REAL*\n"]
    for r in results:
        icon  = "✅" if r["pct"] >= 70 else ("⚠️" if r["pct"] >= 40 else "❌")
        lines.append(f"{icon} *{r['scenario']}* ({r['model']}): {r['score']}/{r['max_score']} ({r['pct']}%) — {r['latency_ms']/1000:.1f}s")
    total  = sum(r["score"] for r in results)
    max_t  = sum(r["max_score"] for r in results)
    pct    = round(total / max_t * 100, 1) if max_t else 0
    lines.append(f"\n*Total: {total}/{max_t} ({pct}%)*")
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="+", default=DEFAULT_SCENARIOS,
                        choices=list(SCENARIO_MAP.keys()))
    parser.add_argument("--model",    default="qwen3.5:9b")
    parser.add_argument("--no-notify", action="store_true",
                        help="Não envia resultado pelo Claudio")
    args = parser.parse_args()

    print(f"\nAgentForge Benchmark — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Modelo: {args.model}  |  Cenários: {args.scenarios}")
    print("=" * 60)

    results = []
    for sid in args.scenarios:
        print(f"\n[{sid}] Iniciando... (agent: {AGENT_MAP[sid].name})")
        r = run_agent_on_scenario(sid, args.model)
        results.append(r)
        print(format_scenario_report(r))

    # Sumário final
    total   = sum(r["score"] for r in results)
    max_t   = sum(r["max_score"] for r in results)
    pct_all = round(total / max_t * 100, 1) if max_t else 0
    print(f"\n{'='*60}")
    print(f"  TOTAL: {total}/{max_t} ({pct_all}%)")
    print(f"{'='*60}")

    if not args.no_notify:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from agentforge.tools.send_claudio import send_claudio
        msg = build_telegram_summary(results)
        resp = send_claudio(msg)
        print(f"\n[Claudio] {resp}")

    # Salva sumário JSON
    RESULTS_BASE.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary_path = RESULTS_BASE / f"summary_{ts}.json"
    summary_path.write_text(json.dumps({
        "model": args.model,
        "scenarios": args.scenarios,
        "total_score": total,
        "total_max": max_t,
        "total_pct": pct_all,
        "results": results,
    }, ensure_ascii=False, indent=2, default=str))
    print(f"\nSumário salvo em: {summary_path}")


if __name__ == "__main__":
    main()
