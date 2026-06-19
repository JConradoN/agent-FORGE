#!/usr/bin/env bash
# =============================================================================
# Funil completo FORGE F1-F5 + REAL P1-P4 para claudio-9b-v3
# Usa os runners originais dos repos forge/ e real/ (mesmo harness dos outros modelos)
# =============================================================================
set -uo pipefail

MODEL="claudio-9b-v3"
FORGE_DIR="$HOME/repos/estudo/forge"
REAL_DIR="$HOME/repos/estudo/real"
LOG="$HOME/full_benchmark_claudio_v2_$(date +%Y%m%d_%H%M).log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

drain_vram() {
    curl -s http://localhost:11434/api/ps \
      | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" \
      2>/dev/null \
    | while read -r m; do
        curl -s http://localhost:11434/api/chat -d "{\"model\":\"$m\",\"keep_alive\":0}" > /dev/null
        log "  descarregado: $m"
      done
    sleep 3
}

log "========================================================"
log "  FORGE + REAL — $MODEL"
log "  Log: $LOG"
log "========================================================"

# ── FORGE F1-F5 ──────────────────────────────────────────────────────────────
log ""
log "════ FORGE F1-F5 ════"
cd "$FORGE_DIR"

for SCENARIO in F1 F2 F3 F4 F5; do
    log ""
    log ">>> FORGE $SCENARIO"
    drain_vram

    if python3 -u scripts/forge_runner.py "$MODEL" --scenario "$SCENARIO" --runs 1 \
        2>&1 | tee -a "$LOG"; then
        log "  [OK] FORGE $SCENARIO"
    else
        log "  [ERRO] FORGE $SCENARIO (exit $?)"
    fi
done

# ── SPA server para P2 ───────────────────────────────────────────────────────
log ""
log "════ REAL P1-P4 ════"
log "Iniciando SPA server (port 8765) para P2..."
pkill -f "serve_spa.py" 2>/dev/null || true
cd "$REAL_DIR"
python3 scripts/serve_spa.py >> /tmp/real_spa_claudio.log 2>&1 &
SPA_PID=$!
log "  SPA PID: $SPA_PID"
sleep 2

cleanup_spa() {
    log "Encerrando SPA server (PID $SPA_PID)..."
    kill "$SPA_PID" 2>/dev/null || true
}
trap cleanup_spa EXIT TERM INT

# ── REAL P1-P4 ───────────────────────────────────────────────────────────────
for SCENARIO in P1 P2 P3 P4; do
    log ""
    log ">>> REAL $SCENARIO"
    drain_vram

    if python3 -u scripts/real_runner.py "$MODEL" --scenario "$SCENARIO" --runs 1 \
        2>&1 | tee -a "$LOG"; then
        log "  [OK] REAL $SCENARIO"
    else
        log "  [ERRO] REAL $SCENARIO (exit $?)"
    fi
done

log ""
log "========================================================"
log "  CONCLUÍDO"
log "  FORGE: $FORGE_DIR/results/F{1-5}/$MODEL/"
log "  REAL:  $REAL_DIR/results/P{1-4}/$MODEL/"
log "========================================================"
