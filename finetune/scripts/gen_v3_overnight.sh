#!/bin/bash
# Geração overnight do dataset V3 via Agy
# 300 exemplos: 140 gaps benchmark + 160 generalização (schema-driven, discovery, create_then_use, recovery)
#
# Uso: bash finetune/scripts/gen_v3_overnight.sh [lote_inicial]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SPEC_FILE="$REPO_ROOT/finetune/gemini_synth/AGY_AGENTFORGE_V3.md"
OUTPUT="$REPO_ROOT/finetune/dataset/synth_v3_overnight.jsonl"
LOG="$REPO_ROOT/finetune/logs/gen_v3_$(date +%Y%m%d_%H%M%S).log"

BATCH_SIZE=20
TOTAL_TARGET=300
START_LOTE=${1:-1}
PAUSE_SECS=60

SPEC=$(cat "$SPEC_FILE")

mkdir -p "$(dirname "$LOG")"
touch "$OUTPUT"

echo "[$(date)] ================================================" | tee -a "$LOG"
echo "[$(date)] Dataset V3 overnight — AgentForge generalista"   | tee -a "$LOG"
echo "[$(date)] Alvo: $TOTAL_TARGET ex | Lotes de $BATCH_SIZE"  | tee -a "$LOG"
echo "[$(date)] Output: $OUTPUT"                                  | tee -a "$LOG"
echo "[$(date)] ================================================" | tee -a "$LOG"

# Mapa de categorias por lote (15 lotes × 20 = 300 exemplos)
# Lotes  1-2  : write_large_file_site         (40 ex)
# Lotes  3-4  : write_large_file_report       (40 ex)
# Lote   5    : code_review_report            (15 ex) + quality_report (5 ex)
# Lote   6    : quality_report               (5 ex restantes) + architecture_analysis (10 ex restantes) = espera 20
# Lote   7    : pytest_sqlite_isolation       (15 ex) + pytest_file_isolation (5 ex)
# Lote   8    : pytest_file_isolation (5) + market_analysis_signals (10) + completion_after_reflection (5)
# Lote   9    : completion_after_reflection (5) + general_reasoning (15)
# Lotes 10-11 : schema_driven_use             (40 ex, 2 lotes de 20)
# Lotes 12-13 : tool_discovery                (40 ex, 2 lotes de 20) ... Wait, that's too many
# Rebalancing:
# Lotes 1-2 (40): write_large_file_site
# Lotes 3-4 (40): write_large_file_report
# Lote  5   (20): code_review_report(15) + quality_report(5)
# Lote  6   (20): quality_report(5) + architecture_analysis(10) + pytest_sqlite(5)
# Lote  7   (20): pytest_sqlite(10) + pytest_file(10)
# Lote  8   (20): market_analysis(10) + completion_reflection(10)
# Lote  9   (20): general_reasoning(20)
# Lotes 10-11 (40): schema_driven_use(40 + 10 extra?)
# Hmm, let me just do 15 lotes of 20 = 300 total

for ((lote=START_LOTE; lote<=15; lote++)); do
    START_ID=$(( (lote-1)*BATCH_SIZE + 1 ))
    END_ID=$(( lote*BATCH_SIZE ))

    CURRENT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
    if [ "$CURRENT" -ge "$TOTAL_TARGET" ]; then
        echo "[$(date)] Atingido alvo de $TOTAL_TARGET exemplos. Encerrando." | tee -a "$LOG"
        break
    fi

    START_ID_FMT=$(printf "v3-c%03d" $START_ID)
    END_ID_FMT=$(printf "v3-c%03d" $END_ID)
    echo "[$(date)] Lote $lote/15: $START_ID_FMT → $END_ID_FMT (acumulado: $CURRENT/$TOTAL_TARGET)" | tee -a "$LOG"

    # Distribuição de categorias por lote
    case $lote in
        1|2)  CAT="write_large_file_site — site HTML completo via write_file + append_file + servidor. OBRIGATÓRIO: write_file(estrutura) + append_file(CSS) + append_file(JS) + run_bash(servidor) + 'PÁGINA PUBLICADA'" ;;
        3|4)  CAT="write_large_file_report — relatório/documento longo via write_file(cabeçalho) + múltiplos append_file(seções). NUNCA uma chamada >4KB. Termina com 'RELATÓRIO GERADO' ou 'ANÁLISE CONCLUÍDA'" ;;
        5)    CAT="code_review_report (15 ex) e quality_report (5 ex) — OBRIGATÓRIO: read_file para ler código + write_file para relatório estruturado + 'REVISÃO CONCLUÍDA'" ;;
        6)    CAT="quality_report (10 ex) e architecture_analysis (10 ex) — análise aprofundada via run_bash/read_file seguida de write_file com relatório. Frase obrigatória: 'ANÁLISE CONCLUÍDA'" ;;
        7)    CAT="pytest_sqlite_isolation (15 ex) e pytest_file_isolation (5 ex) — OBRIGATÓRIO: @pytest.fixture com tmp_path para isolar estado entre testes. Modelo usa read_file para verificar nomes de funções antes de escrever os testes" ;;
        8)    CAT="market_analysis_signals (10 ex: headings COTAÇÕES e RECOMENDAÇÃO exatos + 'ANÁLISE CONCLUÍDA') e completion_after_reflection (10 ex: assistente emite resposta sem frase → engine injeta must_compliance → assistente corrige)" ;;
        9)    CAT="general_reasoning — 10 ex technical_analysis_no_tool (análise técnica profunda SEM tool calls, 300-600 palavras, PT-BR) + 10 ex code_explanation_no_tool (explicação de código/algoritmo SEM tools)" ;;
        10|11) CAT="tool_generalization: schema_driven_use — modelo recebe tool com nome inventado no schema e a usa corretamente SEM questionar. Tools incomuns: harvest_metrics, diff_snapshots, emit_webhook, chunk_text, score_relevance, extract_entities, pin_memory, resolve_alias, schedule_task, validate_schema. 5 ex por tool" ;;
        12|13) CAT="tool_generalization: tool_discovery — modelo NÃO sabe quais tools existem, descobre via run_bash('ls tools/') + read_file para ler spec da tool, depois usa corretamente. Tópicos: buscar notícias, processar logs, enviar notificação, escanear diretório, criar agente, fazer backup" ;;
        14)   CAT="tool_generalization: create_then_use — modelo cria nova tool via write_file('tools/nome.py', código com ToolSpec) + run_bash para verificar, depois INVOCA a tool que criou na mesma sessão. Tipos: parser de formato, calculadora de métrica, wrapper de API, ferramenta de análise de texto" ;;
        15)   CAT="tool_generalization: error_recovery_tool — modelo tenta tool, recebe erro ('tool not found' / 'wrong params' / 'timeout'), adapta estratégia: ls tools/ para descobrir alternativa, read_file para ler schema correto, dividir em chamadas menores. SEMPRE completa a tarefa no final" ;;
    esac

    EXTRA_RULES=""
    case $lote in
        1|2|3|4) EXTRA_RULES="- write_file/append_file: NUNCA mais de 4KB por chamada
- write_large_file: OBRIGATÓRIO write_file + pelo menos 2 append_file" ;;
        5|6)  EXTRA_RULES="- code_analysis: OBRIGATÓRIO pelo menos 1 read_file + pelo menos 1 write_file de relatório" ;;
        7)    EXTRA_RULES="- pytest: OBRIGATÓRIO @pytest.fixture com tmp_path em todos os testes que usam estado compartilhado" ;;
        10|11|12|13|14|15) EXTRA_RULES="- tool_generalization: modelo NUNCA questiona se a tool existe — usa baseado no schema
- schema_driven: tool name pode ser qualquer coisa; o modelo usa pelo description+parameters
- discovery: modelo SEMPRE faz run_bash primeiro para descobrir tools disponíveis antes de usá-las
- create_then_use: a tool criada DEVE ser invocada na mesma sessão" ;;
    esac

    PROMPT="Gere exatamente $BATCH_SIZE exemplos de dataset para fine-tuning de LLM agentico (IDs $START_ID_FMT a $END_ID_FMT).

FOCO DESTE LOTE: $CAT

REGRAS CRÍTICAS (TODAS obrigatórias):
- IDs sequenciais: $START_ID_FMT até $END_ID_FMT
- Salve via APPEND no arquivo: $OUTPUT
- Cada linha = 1 JSON válido sem quebra de linha interna (use \\n, nunca newline literal dentro de string)
- tool_calls[].function.arguments é sempre dict (nunca string JSON)
- role tool sempre tem campo 'name' com nome da ferramenta
- Última mensagem sempre role=assistant com texto de resposta final
$EXTRA_RULES

Após gerar e salvar TODOS os $BATCH_SIZE exemplos, execute:
python3 -c \"lines=open('$OUTPUT').readlines(); print(f'Total acumulado: {len(lines)} exemplos')\"

SPEC COMPLETA (use para detalhes de formato e exemplos canônicos):
$SPEC"

    if agy --print-timeout 18m --print "$PROMPT" >> "$LOG" 2>&1; then
        NEW_TOTAL=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
        echo "[$(date)] Lote $lote OK — total: $NEW_TOTAL/$TOTAL_TARGET exemplos" | tee -a "$LOG"
    else
        EXIT_CODE=$?
        echo "[$(date)] ERRO no lote $lote (exit $EXIT_CODE) — aguardando 90s e tentando continuar" | tee -a "$LOG"
        sleep 90
        continue
    fi

    REMAINING=$((TOTAL_TARGET - $(wc -l < "$OUTPUT" 2>/dev/null || echo 0)))
    if [ "$REMAINING" -le 0 ]; then
        echo "[$(date)] Alvo atingido. Encerrando." | tee -a "$LOG"
        break
    fi

    echo "[$(date)] Pausa de ${PAUSE_SECS}s antes do próximo lote..." | tee -a "$LOG"
    sleep "$PAUSE_SECS"
done

FINAL=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
echo ""                                                              | tee -a "$LOG"
echo "[$(date)] ================================================"  | tee -a "$LOG"
echo "[$(date)] CONCLUÍDO — $FINAL exemplos em $OUTPUT"            | tee -a "$LOG"
echo "[$(date)] Próximo passo: bash finetune/scripts/assemble_v3_dataset.sh" | tee -a "$LOG"
echo "[$(date)] Log completo: $LOG"                                 | tee -a "$LOG"
echo "[$(date)] ================================================"  | tee -a "$LOG"
# Fim do script principal — não adicionar nada abaixo
