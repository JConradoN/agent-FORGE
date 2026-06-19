#!/bin/bash
# Extensão overnight — mais exemplos de generalização após os 300 iniciais
# Foco: schema_driven_use e tool_discovery (categorias mais finas)
# +200 exemplos → total V3 = 500

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SPEC_FILE="$REPO_ROOT/finetune/gemini_synth/AGY_AGENTFORGE_V3.md"
OUTPUT="$REPO_ROOT/finetune/dataset/synth_v3_overnight.jsonl"
LOG="$REPO_ROOT/finetune/logs/gen_v3_ext_$(date +%Y%m%d_%H%M%S).log"

BATCH_SIZE=20
EXTENSION_TARGET=500
PAUSE_SECS=60
SPEC=$(cat "$SPEC_FILE")

mkdir -p "$(dirname "$LOG")"

START_COUNT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
FINAL_TARGET=$((START_COUNT + EXTENSION_TARGET))
START_ID=$((START_COUNT + 1))

echo "[$(date)] ================================================" | tee -a "$LOG"
echo "[$(date)] V3 Extension — +$EXTENSION_TARGET exemplos de generalização" | tee -a "$LOG"
echo "[$(date)] Início: $START_COUNT | Meta: $FINAL_TARGET" | tee -a "$LOG"
echo "[$(date)] ================================================" | tee -a "$LOG"

for lote in $(seq 1 25); do
    CURRENT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
    [ "$CURRENT" -ge "$FINAL_TARGET" ] && { echo "[$(date)] Meta atingida." | tee -a "$LOG"; break; }

    ID_START=$((START_COUNT + (lote-1)*BATCH_SIZE + 1))
    ID_END=$((ID_START + BATCH_SIZE - 1))
    START_FMT=$(printf "v3-ext-%03d" $ID_START)
    END_FMT=$(printf "v3-ext-%03d" $ID_END)

    echo "[$(date)] Lote ext-$lote: $START_FMT → $END_FMT (acumulado: $CURRENT/$FINAL_TARGET)" | tee -a "$LOG"

    case $lote in
        1|2|3) CAT="tool_generalization: schema_driven_use — 20 exemplos NOVOS com tools diferentes das anteriores. Tools: analyze_tone, merge_datasets, watch_file, replay_events, compute_embedding, route_message, persist_checkpoint, hydrate_template, benchmark_latency, classify_intent. 2 ex por tool." ;;
        4|5|6) CAT="tool_generalization: tool_discovery — 20 exemplos onde o modelo descobre tools via run_bash ANTES de agir. Cenários: monitorar recursos, compilar relatório diário, processar fila, integrar com serviço, auto-diagnosticar sistema, indexar documentos, sincronizar estado entre agentes, enviar notificação condicional." ;;
        7|8)   CAT="tool_generalization: create_then_use — 10 exemplos de tools criadas com write_file e imediatamente invocadas. Tools: rate_limiter, text_diff, semantic_search_local, log_aggregator, config_validator. ToolSpec Python correto obrigatório." ;;
        9|10)  CAT="tool_generalization: error_recovery_tool — 10 exemplos de recovery real. Cenários: tool retorna formato errado (parseia manualmente), tool exige auth (verifica env), tool retorna vazio (tenta alternativa), tool deprecada (migra para nova). Sempre completa a tarefa." ;;
        11|12) CAT="write_large_file — documentação técnica longa: API reference, guia de integração, changelog completo. Padrão: write_file(intro) + 3+ append_file(seções) + run_bash(validar) + 'DOCUMENTAÇÃO GERADA'. NUNCA >4KB por chamada." ;;
        13|14) CAT="code_review_report — análise de código Python/Go/JS via read_file + write_file com relatório estructurado. Foco em: bugs de segurança, complexidade ciclomática, cobertura de testes, coupling. Terminar com 'REVISÃO CONCLUÍDA'." ;;
        15|16) CAT="tool_generalization: schema_driven_use — 20 ex com tools de domínios diferentes: ML/data (train_model, evaluate_metrics, export_artifact), DevOps (deploy_service, rollback_release, scale_pods), infra (check_disk, kill_process, rotate_logs). 3-4 ex por domínio." ;;
        17|18) CAT="tool_generalization: tool_discovery multi-step — cenários onde o modelo descobre tools, lê spec, constata limitação, busca alternativa e completa com segunda tool. 20 exemplos com pelo menos 2 tools diferentes descobertas por conversa." ;;
        19|20) CAT="general_reasoning — 10 ex de análise técnica aprofundada SEM tools (300-600 palavras PT-BR) + 10 ex de debugging: usuário descreve erro, modelo analisa causa raiz e propõe fix detalhado, sem rodar código." ;;
        21|22) CAT="completion_after_reflection — 20 exemplos de multi-turn: usuário pede tarefa, assistente inicia SEM frase obrigatória, engine injeta must_compliance, assistente corrige adicionando a frase exata. Frases variadas: 'ANÁLISE CONCLUÍDA', 'REVISÃO CONCLUÍDA', 'RELATÓRIO GERADO', 'PÁGINA PUBLICADA'." ;;
        23|24) CAT="tool_generalization: create_then_use avançado — 10 ex onde a tool criada recebe dados de uma tool anterior (pipeline). Exemplo: fetch_data → write_file(processor.py com ToolSpec) → invocar processor com os dados. Código Python funcional obrigatório." ;;
        25)    CAT="mix final — 5 ex de cada: schema_driven_use (tools de IoT/embedded), tool_discovery (ambiente de produção sem docs), create_then_use (wrapper de API externa), error_recovery (timeout cascata). Total 20 ex variados." ;;
    esac

    PROMPT="Gere exatamente $BATCH_SIZE exemplos (IDs $START_FMT a $END_FMT).

FOCO: $CAT

REGRAS CRÍTICAS:
- IDs: $START_FMT até $END_FMT
- APPEND em: $OUTPUT
- 1 JSON válido por linha, sem newline literal dentro de strings (use \\n)
- tool_calls[].function.arguments sempre dict
- role tool sempre tem campo name
- Modelo NUNCA questiona se tool existe — usa baseado no schema

Após salvar:
python3 -c \"lines=open('$OUTPUT').readlines(); print(f'Total acumulado: {len(lines)} exemplos')\"

SPEC:
$SPEC"

    if agy --print-timeout 18m --print "$PROMPT" >> "$LOG" 2>&1; then
        NEW=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
        echo "[$(date)] Lote ext-$lote OK — total: $NEW/$FINAL_TARGET" | tee -a "$LOG"
    else
        echo "[$(date)] ERRO no lote ext-$lote — aguardando 90s" | tee -a "$LOG"
        sleep 90; continue
    fi

    sleep "$PAUSE_SECS"
done

FINAL=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
echo "[$(date)] EXTENSÃO CONCLUÍDA — $FINAL exemplos totais em $OUTPUT" | tee -a "$LOG"
