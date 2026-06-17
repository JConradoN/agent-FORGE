#!/bin/bash
# run_batch.sh — executa uma bateria de geração sintética
# Para Cláudio durante a geração, reinicia ao terminar.
#
# Uso:
#   ./run_batch.sh 1         # bateria 1 (500 exemplos)
#   ./run_batch.sh 2         # bateria 2 (usa gold_batch2.jsonl)
#   ./run_batch.sh all       # roda todas as baterias pendentes

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FINETUNE_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$FINETUNE_DIR/.venv/bin/python"
LOG="$FINETUNE_DIR/dataset/batch_run_$(date +%Y%m%d_%H%M).log"

BATCH="${1:-1}"
COUNT=500

echo "[$(date)] Iniciando bateria $BATCH ($COUNT exemplos)" | tee -a "$LOG"

# Para o Cláudio para liberar slot do Ollama
echo "[$(date)] Pausando Cláudio..." | tee -a "$LOG"
systemctl --user stop claudio.service 2>/dev/null && echo "  Cláudio parado" || echo "  Cláudio já estava parado"
sleep 5

# Aguarda slot livre
echo "[$(date)] Aguardando Ollama liberar slot..." | tee -a "$LOG"
for i in $(seq 1 12); do
    BUSY=$(curl -s http://localhost:11434/api/ps | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(any(m.get('processing_count', 0) > 0 for m in d.get('models', [])))
" 2>/dev/null || echo "False")
    if [ "$BUSY" = "False" ]; then
        echo "  Slot livre." | tee -a "$LOG"
        break
    fi
    echo "  Slot ocupado, aguardando 10s ($i/12)..." | tee -a "$LOG"
    sleep 10
done

# Gera dataset
echo "[$(date)] Iniciando geração..." | tee -a "$LOG"
"$VENV" "$SCRIPT_DIR/synth_generate.py" \
    --count "$COUNT" \
    --category all \
    --temperature 0.85 \
    2>&1 | tee -a "$LOG"

echo "[$(date)] Geração concluída." | tee -a "$LOG"

# Roda QA automático
echo "[$(date)] Rodando QA..." | tee -a "$LOG"
"$VENV" "$SCRIPT_DIR/qa_dataset.py" 2>&1 | tee -a "$LOG"

# Reinicia Cláudio
echo "[$(date)] Reiniciando Cláudio..." | tee -a "$LOG"
systemctl --user start claudio.service && echo "  Cláudio online" || echo "  [WARN] Cláudio não reiniciou — verifique manualmente"

echo "[$(date)] Bateria $BATCH finalizada. Log: $LOG" | tee -a "$LOG"
