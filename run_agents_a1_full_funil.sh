#!/usr/bin/env bash
# Funil completo — InternScience/Agents-A1 (35B-A3B), teste :8083, thinking=0, ctx 131072
# Adaptado de run_qwen36_35b_full_funil.sh para comparar Agents-A1 vs. campeão qwen3.6-35B-A3B
# ABS + LOP (S1-S4) + FORGE (F1,F2,F4,F5) + REAL (P1,P2,P4) + AgentForge (F3,P3)

set -uo pipefail

MODEL="Agents-A1-Q4_K_M.gguf"
MODEL_SAFE="agents-a1"
MODEL_ID="agents-a1"
TQ_URL="http://localhost:8083"
ABS_DIR="/home/conrado/repos/estudo/agent-benchmark-suite"
LOP_DIR="/home/conrado/repos/estudo/llms-on-prem"
FORGE_DIR="/home/conrado/repos/estudo/forge"
REAL_DIR="/home/conrado/repos/estudo/real"
AF_DIR="/home/conrado/repos/estudo/agents-framework"
SHIM_PID=""
RUNS=3
TIMEOUT=900
TODAY=$(date +%Y-%m-%d)

export LLAMACPP_THINKING_BUDGET=0
export LLAMACPP_ENABLE_THINKING=0

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

tg() {
    python3 -c "
import sys
sys.path.insert(0, '$AF_DIR/src')
from agentforge.tools.send_claudio import send_claudio
print(send_claudio('''$1'''))
" 2>/dev/null
}

start_shim() {
    docker stop ollama >/dev/null 2>&1 || true
    LLAMACPP_HOST="$TQ_URL" LLAMACPP_TIMEOUT="$TIMEOUT" LLAMACPP_ENABLE_THINKING=0 \
        python3 "$AF_DIR/scripts/ollama_shim.py" &
    SHIM_PID=$!
    sleep 3
    curl -sf http://localhost:11434/health | grep -q "ok"
}

stop_shim() {
    [[ -n "$SHIM_PID" ]] && kill "$SHIM_PID" 2>/dev/null || true
    SHIM_PID=""
}

_cleanup() {
    stop_shim
    docker start ollama >/dev/null 2>&1 || true
    log "Restaurando produção (docker stop turboquant-test-agents-a1 && docker start turboquant)..."
    docker stop turboquant-test-agents-a1 >/dev/null 2>&1 || true
    docker start turboquant >/dev/null 2>&1 || true
    sleep 5
    if curl -sf http://localhost:8082/health | grep -q ok; then
        log "Produção confirmada saudável."
    else
        log "ALERTA: produção não respondeu saudável após restart — checar manualmente!"
    fi
}
trap '_cleanup' EXIT TERM INT

log "Verificando Agents-A1 (teste) em $TQ_URL ..."
if ! curl -sf "$TQ_URL/health" | grep -q "ok"; then
    log "ERRO: instância de teste não responde. Abortando."
    exit 1
fi

tg "🚀 Funil Agents-A1 iniciado — ABS+LOP+FORGE(F1,F2,F4,F5)+REAL(P1,P2,P4)+AgentForge(F3,P3) — $(date '+%H:%M')"

# ── FASE 1 — ABS ─────────────────────────────────────────────────────────────
log "════ FASE 1 — ABS ════"
OUTDIR="$ABS_DIR/results/bateria_final/$MODEL_SAFE"
mkdir -p "$OUTDIR"
ALL_SCENARIOS=(T1 T2 T3 T4 T5 T6 C1 C2 C3 C4 C5 Q1 Q2 Q2v2 Q3 Q4 L1 L2 L3 M1-A M1-H M2-A M2-H)
cd "$ABS_DIR"
python3 run.py \
    --provider llama-server \
    --base-url "$TQ_URL" \
    --model "$MODEL" \
    --scenario "${ALL_SCENARIOS[@]}" \
    --runs $RUNS \
    --timeout $TIMEOUT \
    --no-think \
    --output-dir "$OUTDIR" \
    && log "ABS OK" || log "ABS FALHOU (continuando)"
tg "📈 ABS (Agents-A1) concluído — $(date '+%H:%M')"

# ── FASE 2 — LOP S1-S4 ──────────────────────────────────────────────────────
log "════ FASE 2 — LOP S1-S4 ════"
start_shim || log "Pulando LOP (shim falhou)"
if [[ -n "$SHIM_PID" ]]; then
    cd "$LOP_DIR"
    SAFE_MODEL=$(echo "$MODEL_ID" | tr ':' '-')
    S1_MARKER="results/benchmarks/S1-${SAFE_MODEL}-${TODAY}-run5.txt"
    [[ -f "$S1_MARKER" ]] && log "LOP S1 skip" || {
        log "LOP S1 start"
        python3 scripts/run-s1-benchmark.py "$MODEL_ID" && log "LOP S1 OK" || log "LOP S1 FALHOU"
    }
    for n in 2 3 4; do
        MARKER="results/benchmarks/S${n}-${SAFE_MODEL}-${TODAY}-summary.md"
        [[ -f "$MARKER" ]] && { log "LOP S${n} skip"; continue; }
        log "LOP S${n} start"
        python3 "scripts/run-s${n}-benchmark.py" "$MODEL_ID" && log "LOP S${n} OK" || log "LOP S${n} FALHOU"
    done
    stop_shim
fi
tg "📊 LOP (Agents-A1) concluído — $(date '+%H:%M')"

# ── FASE 3 — FORGE F1,F2,F4,F5 ──────────────────────────────────────────────
log "════ FASE 3 — FORGE F1,F2,F4,F5 ════"
start_shim || log "Pulando FORGE (shim falhou)"
if [[ -n "$SHIM_PID" ]]; then
    cd "$FORGE_DIR"
    for scenario in F1 F2 F4 F5; do
        log "FORGE $scenario start"
        python3 scripts/forge_runner.py "$MODEL_ID" --scenario "$scenario" --runs 3 \
            && log "FORGE $scenario OK" || log "FORGE $scenario FALHOU (continuando)"
    done
    stop_shim
fi
tg "🔨 FORGE (Agents-A1, F1/F2/F4/F5) concluído — $(date '+%H:%M')"

# ── FASE 4 — REAL P1,P2,P4 ──────────────────────────────────────────────────
log "════ FASE 4 — REAL P1,P2,P4 ════"
start_shim || log "Pulando REAL (shim falhou)"
if [[ -n "$SHIM_PID" ]]; then
    cd "$REAL_DIR"
    pkill -f "serve_spa.py" 2>/dev/null || true
    python3 scripts/serve_spa.py >> /tmp/real_spa_agents_a1.log 2>&1 &
    SPA_PID=$!
    sleep 2
    for scenario in P1 P2 P4; do
        log "REAL $scenario start"
        python3 scripts/real_runner.py "$MODEL_ID" --scenario "$scenario" --runs 3 \
            && log "REAL $scenario OK" || log "REAL $scenario FALHOU (continuando)"
    done
    kill "$SPA_PID" 2>/dev/null || true
    stop_shim
fi
tg "🌐 REAL (Agents-A1, P1/P2/P4) concluído — $(date '+%H:%M')"

# ── FASE 5 — AgentForge F3,P3 ────────────────────────────────────────────────
log "════ FASE 5 — AgentForge F3,P3 ════"
export LLAMACPP_HOST="$TQ_URL"
export LLAMACPP_TIMEOUT="900"
export AGENTFORGE_PROVIDER="llamacpp"
cd "$AF_DIR"
python3 scripts/run_benchmark_eval.py --model "$MODEL_ID" --scenarios F3 P3 --provider llamacpp \
    && log "AgentForge F3,P3 OK" || log "AgentForge F3,P3 FALHOU (continuando)"

log "════ FUNIL AGENTS-A1 COMPLETO ════"
tg "🏁 Funil Agents-A1 COMPLETO — $(date '+%H:%M'). ABS+LOP+FORGE(F1,F2,F4,F5)+REAL(P1,P2,P4)+AgentForge(F3,P3) prontos pra comparar com o campeão 35B-A3B."
