#!/usr/bin/env bash
# ================================================================
# run_claudio_v2_funnel.sh — Funil completo ABS → LOP → FORGE → REAL
# Modelo: claudio-9b-v2 (qwen3.5:9b fine-tuned agentic)
#
# Uso:
#   nohup bash run_claudio_v2_funnel.sh 2>&1 | tee ~/funnel_claudio_v2_$(date +%Y%m%d_%H%M).log &
# ================================================================

set -uo pipefail

MODEL="claudio-9b-v2"
ABS_DIR="/home/conrado/repos/estudo/agent-benchmark-suite"
LOP_DIR="/home/conrado/repos/estudo/llms-on-prem"
AF_DIR="/home/conrado/repos/estudo/agents-framework"
RUNS=3
TIMEOUT=600
TODAY=$(date +%Y-%m-%d)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── Cleanup ───────────────────────────────────────────────────────────────────
_cleanup() {
    log "Cleanup — restaurando ollama-warmup.service..."
    systemctl --user start ollama-warmup.service 2>/dev/null || true
}
trap '_cleanup' EXIT TERM INT

# ── Parar warmup para isolamento ──────────────────────────────────────────────
systemctl --user stop ollama-warmup.service 2>/dev/null || true
log "ollama-warmup.service parado para isolamento"

# ── Funções utilitárias ───────────────────────────────────────────────────────
drain_vram() {
    local loaded
    loaded=$(curl -s http://localhost:11434/api/ps \
        | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" \
        2>/dev/null)
    if [[ -n "$loaded" ]]; then
        while IFS= read -r m; do
            log "  Descarregando: $m"
            curl -s http://localhost:11434/api/chat \
                -d "{\"model\":\"$m\",\"keep_alive\":0}" > /dev/null
        done <<< "$loaded"
    fi
    local attempts=0
    while [[ $(curl -s http://localhost:11434/api/ps \
            | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" \
            2>/dev/null) -gt 0 ]]; do
        sleep 2
        attempts=$((attempts + 1))
        [[ $attempts -ge 15 ]] && break
    done
}

warmup_model() {
    drain_vram
    log "  Warmup: $MODEL"
    curl -s http://localhost:11434/api/chat \
        -d "{\"model\":\"$MODEL\",\"stream\":false,
             \"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],
             \"options\":{\"num_predict\":3}}" \
        > /dev/null
    log "  Warmup OK"
}

# ════════════════════════════════════════════════════════════════════════════
# FASE 1 — ABS (T C Q L M, 3 runs, --no-think-prefix)
# ════════════════════════════════════════════════════════════════════════════
log "════════════════════════════════════════════════════"
log "FASE 1 — ABS direct (T C Q L M, runs=${RUNS})"
log "════════════════════════════════════════════════════"

MS=$(echo "$MODEL" | tr ':/' '__')
OUTDIR="$ABS_DIR/results/bateria_final/$(echo "$MODEL" | sed 's|[:/]|_|g')"
mkdir -p "$OUTDIR"

ALL_SCENARIOS=(T1 T2 T3 T4 T5 T6 C1 C2 C3 C4 C5 Q1 Q2 Q2v2 Q3 Q4 L1 L2 L3 M1-A M1-H M2-A M2-H)
INCOMPLETE=()
for sc in "${ALL_SCENARIOS[@]}"; do
    f="$OUTDIR/run_${sc}_${MS}.jsonl"
    if [[ ! -f "$f" ]] || [[ $(wc -l < "$f") -lt $RUNS ]]; then
        INCOMPLETE+=("$sc")
    fi
done

if [[ ${#INCOMPLETE[@]} -eq 0 ]]; then
    log "ABS skip — todos cenários já completos"
else
    log "ABS: ${#INCOMPLETE[@]} cenários pendentes: ${INCOMPLETE[*]}"
    warmup_model
    cd "$ABS_DIR"
    python3 run.py \
        --provider   ollama \
        --model      "$MODEL" \
        --scenario   "${INCOMPLETE[@]}" \
        --runs       "$RUNS" \
        --timeout    "$TIMEOUT" \
        --output-dir "$OUTDIR" \
        --no-think-prefix \
        && log "ABS OK" \
        || log "ABS FALHOU (continuando)"
fi

# ════════════════════════════════════════════════════════════════════════════
# FASE 2 — LOP S1–S4
# ════════════════════════════════════════════════════════════════════════════
log "════════════════════════════════════════════════════"
log "FASE 2 — LOP S1–S4"
log "════════════════════════════════════════════════════"

SAFE_MODEL=$(echo "$MODEL" | tr ':' '-' | tr '/' '_')
cd "$LOP_DIR"
drain_vram

# S1
S1_MARKER="results/benchmarks/S1-${SAFE_MODEL}-${TODAY}-run5.txt"
if [[ -f "$S1_MARKER" ]]; then
    log "LOP S1 skip"
    warmup_model
else
    log "LOP S1 start"
    warmup_model
    bash scripts/run-s1-benchmark.sh "$MODEL" \
        && log "LOP S1 OK" \
        || log "LOP S1 FALHOU (continuando)"
fi

# S2–S4
for n in 2 3 4; do
    MARKER="results/benchmarks/S${n}-${SAFE_MODEL}-${TODAY}-summary.md"
    if [[ -f "$MARKER" ]]; then
        log "LOP S${n} skip"
        continue
    fi
    log "LOP S${n} start"
    python3 "scripts/run-s${n}-benchmark.py" "$MODEL" \
        && log "LOP S${n} OK" \
        || log "LOP S${n} FALHOU (continuando)"
done

# ════════════════════════════════════════════════════════════════════════════
# FASE 3 — FORGE F3
# ════════════════════════════════════════════════════════════════════════════
log "════════════════════════════════════════════════════"
log "FASE 3 — FORGE F3"
log "════════════════════════════════════════════════════"

drain_vram
cd "$AF_DIR"
python3 scripts/run_benchmark_eval.py \
    --model     "$MODEL" \
    --scenarios F3 \
    && log "FORGE F3 OK" \
    || log "FORGE F3 FALHOU (continuando)"

# ════════════════════════════════════════════════════════════════════════════
# FASE 4 — REAL P3 + P4
# ════════════════════════════════════════════════════════════════════════════
log "════════════════════════════════════════════════════"
log "FASE 4 — REAL P3 + P4"
log "════════════════════════════════════════════════════"

python3 scripts/run_benchmark_eval.py \
    --model     "$MODEL" \
    --scenarios P3 P4 \
    && log "REAL P3+P4 OK" \
    || log "REAL P3+P4 FALHOU (continuando)"

# ════════════════════════════════════════════════════════════════════════════
log "════════════════════════════════════════════════════"
log "FUNIL CONCLUÍDO — claudio-9b-v2"
log "  ABS    → $ABS_DIR/results/bateria_final/claudio-9b-v2/"
log "  LOP    → $LOP_DIR/results/benchmarks/"
log "  FORGE  → $AF_DIR/benchmark_results/F3/claudio-9b-v2/"
log "  REAL   → $AF_DIR/benchmark_results/P3/ P4/claudio-9b-v2/"
log "════════════════════════════════════════════════════"
