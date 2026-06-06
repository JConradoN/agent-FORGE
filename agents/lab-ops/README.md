# lab-ops — Agente de Referência

Agente operacional para monitoramento de saúde do servidor e inspeção de logs em ambiente de laboratório. É o agente de referência do AgentForge — implementa todos os mecanismos do framework e serve como baseline para validação e benchmarks.

---

## Configuração

| Campo | Valor |
|---|---|
| Modelo | `qwen3.5:9b` |
| Provider | `ollama` |
| Modo | `respond_or_tool` |
| Max ciclos de tool | 3 |
| Memória | `session_summary`, 6 turns |

---

## Ferramentas

| Ferramenta | Obrigatória | Uso |
|---|---|---|
| `collect_system_health` | Sim | CPU, RAM, disco, GPU, processos |
| `read_log_tail` | Não | Últimas linhas de arquivo de log |

### Decisão de tool use

O modelo é instruído via `when_to_use` / `when_not_to_use`:

- `collect_system_health`: usar quando o usuário perguntar sobre saúde do sistema, recursos ou processos
- `read_log_tail`: usar quando o usuário perguntar sobre logs específicos, erros ou eventos recentes

---

## Guardrails

**Must (comportamentos obrigatórios):**
- Sempre executar `collect_system_health` antes de responder sobre saúde do sistema
- Fornecer recomendações objetivas baseadas nos dados
- Usar caminhos absolutos ou relativos ao servidor para logs

**Must-not (proibições verificadas ativamente):**
- Inventar métricas
- Acessar arquivos fora do diretório de logs do servidor
- Alterar qualquer arquivo do sistema

Os guardrails `must_not` são verificados pelo próprio modelo após cada output. Se violado, o runtime reenvia um prompt de correção automaticamente.

---

## Executar

```bash
# CLI direto
agentforge run --agent-dir agents/lab-ops --input "Como está o servidor?"

# Modo legível
agentforge run --agent-dir agents/lab-ops --input "Há erros nos logs?" --mode pretty

# API HTTP (para n8n ou automações)
agentforge serve --agent-dir agents/lab-ops --port 8080

# Bot Telegram
export TELEGRAM_BOT_TOKEN="..."
agentforge telegram --agent-dir agents/lab-ops

# Ferramentas MCP no Claude Code (.mcp.json já configurado)
agentforge mcp --transport stdio
```

---

## Avaliar

```bash
agentforge eval \
  --agent-dir agents/lab-ops \
  --dataset agents/lab-ops/eval_dataset.yaml
```

O dataset (`eval_dataset.yaml`) contém 8 casos de teste cobrindo:
- Consulta de saúde geral do sistema
- Análise de uso de recursos específicos (CPU, RAM, GPU)
- Inspeção de logs
- Diagnóstico de processos
- Questões fora de escopo (deve recusar ou redirecionar)

Resultados salvos em `agents/lab-ops/eval_runs/<timestamp>.jsonl`.

---

## Estrutura de arquivos

```
agents/lab-ops/
├── agent.yaml         # Spec (fonte de verdade)
├── system_prompt.md   # Prompt gerado — não editar manualmente
├── runtime.yaml       # Parâmetros de execução gerados
├── tools.yaml         # Schema de ferramentas gerado
├── eval.yaml          # Configuração de avaliação gerada
├── eval_dataset.yaml  # 8 casos de teste mantidos manualmente
├── history.json       # Histórico multi-turn (gerado em runtime)
└── runs/
    └── runs.jsonl     # Log de execuções (append-only, gerado em runtime)
```

---

## Por que lab-ops é o agente de referência

- **Cobre todos os mecanismos**: tool calling model-driven, loop guard, guardrails ativos, reflexão, memória multi-turn, logging, eval
- **Domínio controlado**: infra local tem estado verificável — fácil validar se a resposta é baseada em dados reais
- **Guardrails não-triviais**: `must_not: inventar métricas` testa se o modelo alucinat quando as ferramentas falham
- **Dataset de eval estruturado**: 8 casos com notas sobre comportamento esperado servem como regression suite

---

## Regenerar artefatos

Se o `agent.yaml` for modificado, regenere os artefatos:

```bash
agentforge generate --path agents/lab-ops/agent.yaml
```

Isso atualiza `system_prompt.md`, `runtime.yaml`, `tools.yaml` e `eval.yaml`. O `eval_dataset.yaml` é mantido manualmente e não é sobrescrito.
