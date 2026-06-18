#!/bin/bash
# Gera dataset agentforge_v2 em lotes de 30 com pausa entre lotes.
# Uso: bash finetune/scripts/gen_agentforge_v2.sh [lote_inicial]
# Exemplo: bash finetune/scripts/gen_agentforge_v2.sh 2   (começa do lote 2, ou seja v2-c031)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SPEC_FILE="$REPO_ROOT/finetune/gemini_synth/AGY_AGENTFORGE_V2.md"
OUTPUT="$REPO_ROOT/finetune/dataset/synth_agentforge_v2.jsonl"
LOG="$REPO_ROOT/finetune/logs/gen_v2_$(date +%Y%m%d_%H%M%S).log"

BATCH_SIZE=30
TOTAL_TARGET=1350
START_LOTE=${1:-2}   # lote 1 já foi gerado manualmente
PAUSE_SECS=75        # 75s entre lotes para não queimar rate limit

SPEC=$(cat "$SPEC_FILE")

mkdir -p "$(dirname "$LOG")"
echo "[$(date)] Iniciando geração a partir do lote $START_LOTE" | tee -a "$LOG"
echo "[$(date)] Alvo: $TOTAL_TARGET exemplos | Lotes de $BATCH_SIZE | Pausa: ${PAUSE_SECS}s" | tee -a "$LOG"

for ((lote=START_LOTE; lote<=45; lote++)); do
    START_ID=$(( (lote-1)*BATCH_SIZE + 1 ))
    END_ID=$(( lote*BATCH_SIZE ))

    # Verifica quantos já temos
    CURRENT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
    if [ "$CURRENT" -ge "$TOTAL_TARGET" ]; then
        echo "[$(date)] Atingido alvo de $TOTAL_TARGET exemplos. Encerrando." | tee -a "$LOG"
        break
    fi

    START_ID_FMT=$(printf "v2-c%03d" $START_ID)
    END_ID_FMT=$(printf "v2-c%03d" $END_ID)
    echo "[$(date)] Lote $lote: $START_ID_FMT → $END_ID_FMT (total atual: $CURRENT)" | tee -a "$LOG"

    # Determina categorias para este lote baseado na posição
    if   [ $lote -le  7 ]; then CAT="tool_chain (tool_chain_short, tool_chain_medium, tool_chain_dependent)"
    elif [ $lote -le 12 ]; then CAT="completion_signal (completion_from_must_rules, completion_from_hint, completion_partial)"
    elif [ $lote -le 19 ]; then CAT="must_rules (must_proactive, must_correction_loop, must_complex)"
    elif [ $lote -le 24 ]; then CAT="must_not_guardrails (must_not_proactive, must_not_correction_loop)"
    elif [ $lote -le 29 ]; then CAT="structured_output (json_output, yaml_frontmatter, required_sections)"
    elif [ $lote -le 34 ]; then CAT="error_recovery (tool_error_retry, bash_fix_loop, test_fix_loop)"
    elif [ $lote -le 37 ]; then CAT="memory_usage (memory_read_before_answer, memory_write_after_learning, memory_multi_turn)"
    elif [ $lote -le 40 ]; then CAT="context_compaction"
    elif [ $lote -le 43 ]; then CAT="delegation"
    else                        CAT="no_tool_redirect"
    fi

    PROMPT="Gere exatamente 30 exemplos de dataset para fine-tuning de LLM agentico (IDs $START_ID_FMT a $END_ID_FMT).

FOCO DESTE LOTE: categoria(s) $CAT
Use as subcategorias correspondentes da spec.

REGRAS CRÍTICAS:
- IDs sequenciais: $START_ID_FMT, $(printf 'v2-c%03d' $((START_ID+1))), ..., $END_ID_FMT
- Salve via APPEND no arquivo: $OUTPUT
- Cada linha = 1 JSON válido sem quebra de linha interna
- arguments sempre dict (nunca string JSON)
- role tool sempre tem campo name
- Verifique completion phrases (case-sensitive)
- must_not_correction_loop: use o formato EXATO do engine

Após gerar e salvar, execute:
python3 -c \"lines=open('$OUTPUT').readlines(); print(f'Total acumulado: {len(lines)} exemplos')\"

SPEC COMPLETA:
$SPEC"

    if agy --print-timeout 12m --print "$PROMPT" >> "$LOG" 2>&1; then
        NEW_TOTAL=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
        echo "[$(date)] Lote $lote OK — total: $NEW_TOTAL exemplos" | tee -a "$LOG"
    else
        echo "[$(date)] ERRO no lote $lote — aguardando 120s antes de continuar" | tee -a "$LOG"
        sleep 120
        continue
    fi

    if [ $lote -lt 45 ] && [ "$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)" -lt "$TOTAL_TARGET" ]; then
        echo "[$(date)] Aguardando ${PAUSE_SECS}s antes do próximo lote..." | tee -a "$LOG"
        sleep $PAUSE_SECS
    fi
done

FINAL=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
echo "[$(date)] Geração concluída. Total: $FINAL exemplos em $OUTPUT" | tee -a "$LOG"

# Notifica via Claudio quando terminar
python3 -c "
import subprocess, json
msg = f'Dataset AgentForge V2 gerado: $FINAL exemplos em synth_agentforge_v2.jsonl'
print(msg)
" | tee -a "$LOG"
