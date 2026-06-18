#!/bin/bash
# Treino completo do Cláudio 9b com notificação Telegram ao final.
# Rodar como usuário conrado, VRAM deve estar livre antes.

set -euo pipefail

FINETUNE_DIR="/home/conrado/repos/estudo/agents-framework/finetune"
LOG="$FINETUNE_DIR/logs/train_$(date +%Y%m%d_%H%M).log"
TELEGRAM_TOKEN="$(python3 -c "import json; c=json.load(open('$HOME/.aurelia/config/app.json')); print(c['telegram_bot_token'])")"
CHAT_ID="$(python3 -c "import json; c=json.load(open('$HOME/.aurelia/config/app.json')); print(c['telegram_allowed_user_ids'][0])")"

send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d parse_mode="Markdown" \
        -d text="$1" > /dev/null
}

mkdir -p "$FINETUNE_DIR/logs"

echo "[$(date)] Parando ollama-warmup para liberar VRAM..."
systemctl --user stop ollama-warmup.service || true

echo "[$(date)] Iniciando treino completo..."
send_telegram "Treino Claudio 9b iniciado. Estimativa: ~4h. Acompanhe em \`$LOG\`"

START=$(date +%s)

cd "$FINETUNE_DIR"
if .venv/bin/python3 scripts/train.py 2>&1 | tee "$LOG"; then
    END=$(date +%s)
    ELAPSED=$(( (END - START) / 60 ))
    LOSS=$(grep "Loss final:" "$LOG" | tail -1 | grep -oP '[\d.]+$' || echo "?")
    GGUF=$(find output/claudio-9b-v1/gguf -name "*.gguf" 2>/dev/null | head -1 || echo "nao encontrado")

    send_telegram "Treino concluido em ${ELAPSED} min.
Loss final: ${LOSS}
GGUF: \`${GGUF}\`
Proximo passo: ollama create claudio-9b -f output/claudio-9b-v1/gguf/Modelfile"
    echo "[$(date)] Treino concluido com sucesso."
else
    END=$(date +%s)
    ELAPSED=$(( (END - START) / 60 ))
    TAIL=$(tail -5 "$LOG" | tr '\n' ' ')
    send_telegram "ERRO no treino Claudio 9b apos ${ELAPSED} min.
Ultimo log: ${TAIL}"
    echo "[$(date)] ERRO no treino. Ver $LOG"
fi

echo "[$(date)] Reiniciando ollama-warmup..."
systemctl --user start ollama-warmup.service || true
