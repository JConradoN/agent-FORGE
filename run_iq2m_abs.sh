#!/usr/bin/env bash
# ================================================================
# run_iq2m_abs.sh — Fase ABS para Qwen3.6-35B-A3B-UD-IQ2_M (Unsloth, single RTX 3060 12GB)
# Container: iq2m-test (fox-server :8096, --gpus device=0, imagem local-turboquant:latest)
#
# Garante que a produção (turboquant) volta ao ar mesmo se o ABS falhar/travar
# (trap EXIT) — não deixa a máquina sem Cláudio por engano.
#
# Uso:
#   nohup bash run_iq2m_abs.sh > ~/abs_iq2m_$(date +%Y%m%d_%H%M).log 2>&1 &
# ================================================================

set -uo pipefail

MODEL="Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
MODEL_SAFE="qwen36-35b-a3b-iq2m"
TEST_URL="http://localhost:8096"
ABS_DIR="/home/conrado/repos/estudo/agent-benchmark-suite"
RUNS=3
TIMEOUT=2400

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

_cleanup() {
    log "Restaurando produção (docker stop iq2m-test && docker start turboquant)..."
    docker stop iq2m-test >/dev/null 2>&1 || true
    docker start turboquant >/dev/null 2>&1 || true
    sleep 5
    if curl -sf http://localhost:8082/health | grep -q ok; then
        log "Produção confirmada saudável."
    else
        log "ALERTA: produção não respondeu saudável após restart — checar manualmente!"
    fi
}
trap '_cleanup' EXIT TERM INT

log "Verificando $MODEL_SAFE em $TEST_URL ..."
if ! curl -sf "$TEST_URL/health" | grep -q "ok"; then
    log "ERRO: container de teste não está respondendo. Abortando."
    exit 1
fi
log "Container de teste OK."

log "════════════════════════════════════════════════════"
log "ABS — todos cenários, runs=${RUNS}"
log "════════════════════════════════════════════════════"

OUTDIR="$ABS_DIR/results/bateria_final/$MODEL_SAFE"
mkdir -p "$OUTDIR"

ALL_SCENARIOS=(T1 T2 T3 T4 T5 T6 C1 C2 C3 C4 C5 Q1 Q2 Q2v2 Q3 Q4 L1 L2 L3 M1-A M1-H M2-A M2-H)
INCOMPLETE=()
for sc in "${ALL_SCENARIOS[@]}"; do
    f="$OUTDIR/run_${sc}_${MODEL}.jsonl"
    if [[ ! -f "$f" ]] || [[ $(wc -l < "$f") -lt $RUNS ]]; then
        INCOMPLETE+=("$sc")
    fi
done

if [[ ${#INCOMPLETE[@]} -eq 0 ]]; then
    log "ABS skip — todos cenários já completos"
else
    log "ABS: ${#INCOMPLETE[@]} cenários pendentes: ${INCOMPLETE[*]}"
    cd "$ABS_DIR"
    python3 run.py \
        --provider    llama-server \
        --base-url    "$TEST_URL" \
        --model       "$MODEL" \
        --scenario    "${INCOMPLETE[@]}" \
        --runs        "$RUNS" \
        --timeout     "$TIMEOUT" \
        --max-tokens  32768 \
        --output-dir  "$OUTDIR" \
        && log "ABS OK" \
        || log "ABS FALHOU"
fi

log "════════════════════════════════════════════════════"
log "ABS CONCLUÍDO — $MODEL_SAFE → $OUTDIR"
log "════════════════════════════════════════════════════"
