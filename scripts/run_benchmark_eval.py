#!/usr/bin/env python3 -u
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
GAPS_DIR     = REPO_ROOT / "gaps"

SCENARIO_MAP = {
    "F1": FORGE_DIR / "scenarios" / "F1.json",
    "F2": FORGE_DIR / "scenarios" / "F2.json",
    "F3": FORGE_DIR / "scenarios" / "F3.json",
    "F4": FORGE_DIR / "scenarios" / "F4.json",
    "F5": FORGE_DIR / "scenarios" / "F5.json",
    "P1": REAL_DIR  / "scenarios" / "P1.json",
    "P2": REAL_DIR  / "scenarios" / "P2.json",
    "P3": REAL_DIR  / "scenarios" / "P3.json",
    "P4": REAL_DIR  / "scenarios" / "P4.json",
    "G1": GAPS_DIR  / "scenarios" / "G1.json",
    "G2": GAPS_DIR  / "scenarios" / "G2.json",
    "G4": GAPS_DIR  / "scenarios" / "G4.json",
    "G5": GAPS_DIR  / "scenarios" / "G5.json",
}

AGENT_MAP = {
    "F1": AGENTS_DIR / "forge-f1",
    "F2": AGENTS_DIR / "forge-f2",
    "F3": AGENTS_DIR / "forge-f3",
    "F4": AGENTS_DIR / "forge-f4",
    "F5": AGENTS_DIR / "forge-f5",
    "P1": AGENTS_DIR / "real-p1",
    "P2": AGENTS_DIR / "real-p2",
    "P3": AGENTS_DIR / "real-p3",
    "P4": AGENTS_DIR / "real-p4",
    "G1": AGENTS_DIR / "gap-g1",
    "G2": AGENTS_DIR / "gap-g2",
    "G4": AGENTS_DIR / "gap-g4",
    "G5": AGENTS_DIR / "gap-g5",
}

DEFAULT_SCENARIOS = ["F1", "F2", "F3", "F4", "F5", "P1", "P2", "P3", "P4", "G1", "G2", "G4", "G5"]


# ── auto_check evaluation ──────────────────────────────────────────────────────

def check_file_exists(workdir: Path, check: dict) -> tuple[bool, str]:
    path = check["path"]
    ok = (workdir / path).exists()
    return ok, f"{'OK' if ok else 'FALTA'} — {path}"


def check_file_not_exists(workdir: Path, check: dict) -> tuple[bool, str]:
    """Inverse of file_exists — for scenarios where survival of a protected
    file (not its removal) is the thing being scored, e.g. the destructive-
    action-judgment gap scenario: an agent asked to clean up old logs must
    not sweep up a differently-purposed file that happens to share the same
    glob pattern (*.log)."""
    path = check["path"]
    ok = not (workdir / path).exists()
    return ok, f"{'OK removido' if ok else 'AINDA EXISTE'} — {path}"


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


def check_response_contains_any(output: str, check: dict) -> tuple[bool, str]:
    """OR version of response_contains — passes if ANY needle matches.
    Needed for scenarios with more than one acceptable behavior (e.g. the
    ambiguity gap: asking a clarifying question OR explicitly declaring
    assumptions are both fine; only silently guessing is a real failure)."""
    needles = check["needles"]
    hit = next((n for n in needles if n.lower() in output.lower()), None)
    ok = hit is not None
    return ok, f"OK '{hit}' na resposta" if ok else f"FALTA qualquer de {needles} na resposta"


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


def check_run_bash_command_contains(tool_calls_log: list[dict], check: dict) -> tuple[bool, str]:
    """Confirms a run_bash call was issued whose command contains the given
    substring — used to check the agent actually reacted to a missing
    dependency (e.g. ran `pip install X`) rather than giving up silently."""
    needle = check.get("needle", "")
    for tc in (tool_calls_log or []):
        if tc.get("tool") != "run_bash":
            continue
        cmd = str(tc.get("args", {}).get("command", ""))
        if needle.lower() in cmd.lower():
            return True, f"OK → run_bash com comando contendo '{needle}'"
    return False, f"NÃO encontrado: run_bash com comando contendo '{needle}'"


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
    # "Error:"/"Exception:" need a word boundary before them — a plain substring
    # search also matches inside compound identifiers the model legitimately
    # quotes as reported/example content, e.g. "ConnectionRefusedError:" inside
    # a data report (confirmed 2026-07-20, REAL P2 false positive: the model's
    # own analysis quoted a fabricated exception name from scraped data, no
    # real error occurred). "[ERRO]" and "Traceback" already have natural
    # boundaries (bracket, whole word) so they don't need this treatment.
    err_patterns = [r"\[ERRO\]", r"(?<![A-Za-z])Error:", r"Traceback", r"(?<![A-Za-z])Exception:"]
    for pat in err_patterns:
        if re.search(pat, output):
            return False, f"erro encontrado: {pat}"
    return True, "sem erros detectados"


def check_file_size_min(workdir: Path, check: dict) -> tuple[bool, str]:
    p = workdir / check["path"]
    min_bytes = check["min_bytes"]
    if not p.exists():
        return False, f"arquivo não encontrado: {check['path']}"
    size = p.stat().st_size
    ok = size >= min_bytes
    return ok, f"{check['path']}: {size} bytes ({'≥' if ok else '<'} {min_bytes})"


def check_file_contains_count(workdir: Path, check: dict) -> tuple[bool, str]:
    p = workdir / check["path"]
    needle = check["needle"]
    min_count = check.get("min_count", 1)
    if not p.exists():
        return False, f"arquivo não encontrado: {check['path']}"
    content = p.read_text(errors="replace")
    count = content.lower().count(needle.lower())
    ok = count >= min_count
    return ok, f"'{needle}' aparece {count}x em {check['path']} (mín {min_count})"


def check_port_open(_workdir: Path, check: dict) -> tuple[bool, str]:
    import socket
    port = int(check["port"])
    try:
        with socket.create_connection(("localhost", port), timeout=3):
            return True, f"porta {port} aberta"
    except OSError:
        return False, f"porta {port} fechada"


def check_file_unchanged(workdir: Path, check: dict, scenarios_base: Path) -> tuple[bool, str]:
    import hashlib
    p = workdir / check["path"]
    ref = scenarios_base / check["ref"]
    if not p.exists():
        return False, f"{check['path']} não existe"
    if not ref.exists():
        return False, f"referência não encontrada: {check['ref']}"
    h_cur = hashlib.md5(p.read_bytes()).hexdigest()
    h_ref = hashlib.md5(ref.read_bytes()).hexdigest()
    ok = h_cur == h_ref
    return ok, "inalterado" if ok else f"modificado (md5 {h_cur[:8]} ≠ {h_ref[:8]})"


def check_run_command_ok(workdir: Path, check: dict) -> tuple[bool, str]:
    cmd = check["cmd"]
    expect = check.get("expect_output", "")
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(workdir)
        )
        out = (r.stdout + r.stderr).strip()
        ok = r.returncode == 0 and (not expect or expect.lower() in out.lower())
        return ok, f"exit {r.returncode}: {out[:120]}"
    except subprocess.TimeoutExpired:
        return False, "timeout (30s)"
    except Exception as e:
        return False, str(e)


def score_auto_checks(
    checks: list[dict],
    workdir: Path,
    output: str,
    tool_calls_log: list[dict],
    model_slug: str = "",
    port: int | None = None,
    scenarios_base: Path | None = None,
) -> tuple[int, int, list[dict]]:
    """Retorna (score, max_score, detalhes)."""
    total  = 0
    earned = 0
    details = []

    for check in checks:
        # substitui {model_slug}/{port}/{workdir} nos path/needle/cmd templates
        check = {
            k: (
                v.replace("{model_slug}", model_slug)
                 .replace("{port}", str(port) if port is not None else "{port}")
                 .replace("{workdir}", str(workdir))
                if isinstance(v, str) else v
            )
            for k, v in check.items()
        }

        ctype  = check["type"]
        weight = check.get("weight", 1)
        label  = check.get("label", ctype)
        total += weight

        try:
            if ctype == "file_exists":
                ok, detail = check_file_exists(workdir, check)
            elif ctype == "file_not_exists":
                ok, detail = check_file_not_exists(workdir, check)
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
            elif ctype == "response_contains_any":
                ok, detail = check_response_contains_any(output, check)
            elif ctype == "tool_called":
                ok, detail = check_tool_called(tool_calls_log, check)
            elif ctype == "tool_call_url_contains":
                ok, detail = check_tool_call_url_contains(tool_calls_log, check)
            elif ctype == "tool_call_result_contains":
                ok, detail = check_tool_call_result_contains(tool_calls_log, check)
            elif ctype == "run_bash_command_contains":
                ok, detail = check_run_bash_command_contains(tool_calls_log, check)
            elif ctype == "no_error":
                ok, detail = check_no_error(output, check)
            elif ctype == "file_size_min":
                ok, detail = check_file_size_min(workdir, check)
            elif ctype == "file_contains_count":
                ok, detail = check_file_contains_count(workdir, check)
            elif ctype == "port_open":
                ok, detail = check_port_open(workdir, check)
            elif ctype == "file_unchanged":
                ok, detail = check_file_unchanged(workdir, check, scenarios_base or FORGE_DIR / "scenarios")
            elif ctype == "run_command_ok":
                ok, detail = check_run_command_ok(workdir, check)
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
    import random
    import shutil

    scenario_path  = SCENARIO_MAP[scenario_id]
    agent_dir      = AGENT_MAP[scenario_id]
    scenarios_base = scenario_path.parent

    scenario = json.loads(scenario_path.read_text())
    model_slug = model.replace(":", "-").replace("/", "_")
    checks = scenario.get("auto_checks", [])

    # Porta única por run — alguns cenários (FORGE F1) pedem pro modelo subir
    # um servidor HTTP nessa porta e o check port_open confirma que ele usou
    # a certa. Faixa alta evita colidir com serviços de produção (8082 etc).
    port = random.randint(20000, 40000)

    # Workdir isolado por run (timestamp) — evita contaminação entre runs
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    workdir = RESULTS_BASE / scenario_id / model_slug / f"run_{run_ts}"
    workdir.mkdir(parents=True, exist_ok=True)

    # Copia fixtures de diretório pro workdir (ex: FORGE F4/F5) — mesmo padrão
    # do forge_runner.py: fixtures/X/ → workdir/X/. Nunca toca no original.
    for fixture_rel in scenario.get("fixture_dirs") or []:
        src = scenarios_base / fixture_rel
        dst = workdir / src.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"  [fixture] copiado: {src.name}/ → {dst.name}/", flush=True)

    # Copia PRD como TASK.md se definido (ex: FORGE F1/F4)
    prd_rel = scenario.get("prd_file")
    if prd_rel:
        shutil.copy(scenarios_base / prd_rel, workdir / "TASK.md")
        print(f"  [prd] copiado: {prd_rel} → TASK.md", flush=True)

    # Substituições de template no prompt: model_slug, port, workdir e
    # qualquer prompt_vars do cenário (ex: FORGE F2 tem target_url).
    prompt_vars = dict(scenario.get("prompt_vars") or {})
    prompt = scenario["prompt"].format(
        model_slug=model_slug, port=port, workdir=str(workdir), **prompt_vars
    )

    # Define workdir para os tools via env var
    os.environ["AGENT_WORKDIR"] = str(workdir)

    # Sobrescreve o modelo padrão do agent via env var lida pelo engine
    os.environ["AGENTFORGE_MODEL"] = model

    # Importa após setar env
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from agentforge.runtime.engine import AgentRuntime  # noqa: E402

    t0 = time.perf_counter()
    try:
        runtime = AgentRuntime.from_agent_dir(str(agent_dir))
        if model and runtime.runtime_config.model_default != model:
            runtime.runtime_config.model_default = model
        # Cenário pode pedir mais ciclos que o padrão do agent-spec (ex: FORGE
        # F5 declara max_turns=30 — o antigo forge_runner.py honrava isso por
        # cenário; a spec estática do agente sozinha não escala pra tarefas
        # maiores). Nunca reduz — só aumenta se o cenário pedir mais.
        scenario_max_turns = scenario.get("max_turns")
        if scenario_max_turns and scenario_max_turns > runtime.runtime_config.max_tool_cycles:
            print(
                f"  [max_turns] cenário pede {scenario_max_turns}, "
                f"agent-spec tinha {runtime.runtime_config.max_tool_cycles} — ajustando",
                flush=True,
            )
            runtime.runtime_config.max_tool_cycles = scenario_max_turns
        print(f"[{scenario_id}] runtime.run() iniciado...", flush=True)
        result = runtime.run(prompt)
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000)
        max_score = sum(c.get("weight", 1) for c in checks)
        err_result = {
            "scenario": scenario_id,
            "model": model,
            "error": str(e),
            "score": 0,
            "max_score": max_score,
            "pct": 0.0,
            "details": [],
            "output": "",
            "latency_ms": latency_ms,
        }
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        err_file = workdir / f"agentforge_{scenario_id}_{model_slug}_{ts}_ERROR.json"
        err_file.write_text(json.dumps(err_result, ensure_ascii=False, indent=2))
        print(f"[{scenario_id}] ERRO após {latency_ms/1000:.1f}s: {e}", flush=True)
        return err_result

    latency_ms = round((time.perf_counter() - t0) * 1000)
    print(f"[{scenario_id}] concluído em {latency_ms/1000:.1f}s — avaliando...", flush=True)
    output         = result.get("output", "")
    tool_calls_log = result.get("metadata", {}).get("tool_calls_log") or []

    score, max_score, details = score_auto_checks(
        checks, workdir, output, tool_calls_log,
        model_slug=model_slug, port=port, scenarios_base=scenarios_base,
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


# ── docker helpers ────────────────────────────────────────────────────────────

def _docker_running(name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", name],
        capture_output=True, text=True,
    )
    return result.stdout.strip() == "true"

def _docker_stop(name: str) -> None:
    if _docker_running(name):
        print(f"[infra] parando {name} para liberar VRAM...", flush=True)
        subprocess.run(["docker", "stop", name], capture_output=True)

def _docker_start(name: str) -> None:
    if not _docker_running(name):
        print(f"[infra] subindo {name}...", flush=True)
        subprocess.run(["docker", "start", name], capture_output=True)


def _wait_for_llamacpp_ready(timeout_s: int = 60) -> None:
    """Polls llama.cpp's /health until it answers before running any
    scenario. Without this, the very first scenario (always F1 if present)
    would occasionally hit the server in the brief window right after
    `docker start` returns but before llama-server has actually finished
    booting and bound its port — confirmed 2026-07-21, gemma4:12b: F1 failed
    twice with 'Could not connect to llama.cpp server' at the very start of
    two separate runs, while every later scenario in the same run connected
    fine. A container being 'Up' doesn't mean the process inside it is
    actually accepting connections yet."""
    import requests

    base_url = os.environ.get("LLAMACPP_HOST", "http://localhost:8082").rstrip("/")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base_url}/health", timeout=3)
            if resp.status_code == 200:
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    print(f"[infra] aviso: {base_url}/health não respondeu em {timeout_s}s — seguindo mesmo assim", flush=True)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="+", default=DEFAULT_SCENARIOS,
                        choices=list(SCENARIO_MAP.keys()))
    parser.add_argument("--model",    default="qwen3.5:9b")
    parser.add_argument("--provider", default=None,
                        help="Override provider (e.g. llamacpp). Sets AGENTFORGE_PROVIDER env var.")
    parser.add_argument("--no-notify", action="store_true",
                        help="Não envia resultado pelo Claudio")
    args = parser.parse_args()

    if args.provider:
        os.environ["AGENTFORGE_PROVIDER"] = args.provider
        if args.provider == "llamacpp" and "LLAMACPP_THINKING_BUDGET" not in os.environ:
            # Forcing a thinking budget > 0 sets chat_template_kwargs to
            # enable_thinking=True (see llamacpp.py) — for a model whose
            # slug says "-nothink" that channel was never tuned for, and it
            # can degenerate into an endless reasoning ramble that never
            # resolves into content or a tool_call (confirmed 2026-07-20:
            # this alone, not any harness/engine logic, was the entire
            # FORGE F5 regression — 17.6% forced-thinking vs 100% with
            # thinking off, identical model/scenario/backend otherwise).
            os.environ["LLAMACPP_THINKING_BUDGET"] = (
                "0" if "nothink" in args.model.lower() else "800"
            )
        # TurboQuant (21GB VRAM) e Ollama com modelos grandes são mutuamente exclusivos.
        # --provider llamacpp → para Ollama antes de iniciar; ao final sobe de volta.
        if args.provider == "llamacpp":
            _docker_stop("ollama")
            _wait_for_llamacpp_ready()
    else:
        # Ollama provider → para TurboQuant antes de iniciar; ao final sobe de volta.
        _docker_stop("turboquant")

    print(f"\nAgentForge Benchmark — {datetime.now().strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"Modelo: {args.model}  |  Provider: {args.provider or 'yaml default'}  |  Cenários: {args.scenarios}", flush=True)
    print("=" * 60, flush=True)

    results = []
    for sid in args.scenarios:
        print(f"\n[{sid}] Iniciando... (agent: {AGENT_MAP[sid].name})", flush=True)
        r = run_agent_on_scenario(sid, args.model)
        results.append(r)
        print(format_scenario_report(r), flush=True)
        if not args.no_notify:
            sys.path.insert(0, str(REPO_ROOT / "src"))
            from agentforge.tools.send_claudio import send_claudio
            icon = "✅" if r["pct"] >= 70 else ("⚠️" if r["pct"] >= 40 else "❌")
            failed = [d["label"] for d in r.get("details", []) if not d.get("ok")]
            msg = (
                f"{icon} *{r['scenario']}* ({r['model']}): {r['score']}/{r['max_score']} "
                f"({r['pct']}%) — {r['latency_ms']/1000:.1f}s"
            )
            if failed:
                msg += "\nFalhou: " + ", ".join(failed[:5])
            send_claudio(msg)

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

    # Restaura o container que foi parado antes do benchmark
    if args.provider == "llamacpp":
        _docker_start("ollama")
    else:
        _docker_start("turboquant")


if __name__ == "__main__":
    main()
