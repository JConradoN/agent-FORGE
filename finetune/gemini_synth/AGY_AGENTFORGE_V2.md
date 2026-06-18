# AGY_AGENTFORGE_V2 — Dataset Agentico Completo

## Objetivo

Fine-tuning do qwen3.5:9b exclusivamente para comportamento agentico no AgentForge.
Zero exemplos conversacionais. Todo o sinal de treino vai para comportamentos que o engine
realmente executa: tool chains, guardrails, must rules, completion signals, memory, delegation.

**Arquivo de saída:** `/home/conrado/repos/estudo/agents-framework/finetune/dataset/synth_agentforge_v2.jsonl`
**Volume:** 500 exemplos por lote (gere em lotes de 500 para não saturar o contexto)
**IDs:** `v2-c001` em diante
**Formato:** JSONL, uma linha por exemplo, sem quebra de linha dentro do JSON

---

## Como o engine funciona — referência obrigatória

O AgentRuntime monta e executa cada run assim:

```
1. user_input + must_rules → injetados no user message
   Formato: "{input}\n\n### MANDATORY RULES FOR THIS TASK:\n- rule1\n- rule2\n"

2. Loop de tool calling (até max_tool_cycles):
   assistant(tool_calls) → tool(result) → assistant(tool_calls) → ...

3. Se modelo responde sem tool quando tem tools disponíveis:
   engine injeta: "You have not used any tools yet. Do NOT output code or text
   directly — use the available tools to complete the task. Call the appropriate
   tool now to proceed."

4. Após max_cycles → completion_hint:
   "Produce your final response based on the tools executed above.\n\n
   Tools already executed:\n  - tool_name({args})\n\n
   Your response MUST include: 'FRASE_EXATA'"

5. _apply_guardrails (must_not):
   engine detecta violação → injeta:
   "Your previous response violated the following restrictions:\n
   - violação detectada\n\n
   Rewrite your response without violating these restrictions.\n\n
   Original question: {input}\n\n
   Content to rewrite:\n{output_violado}"

6. _check_must_compliance (must):
   engine verifica regras não cumpridas → injeta:
   "Your response is incomplete. The following mandatory rules were not met:\n
   - regra não cumprida\n\n
   Complete your response by including the missing items."
```

## Formato de cada exemplo

```json
{
  "id": "v2-c001",
  "source": "synthetic_agy_v2",
  "category": "agentforge",
  "subcategory": "<uma das categorias abaixo>",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "...", "arguments": {...}}}]},
    {"role": "tool", "content": "...", "name": "..."},
    {"role": "assistant", "content": "...resposta final..."}
  ]
}
```

**Regras de formato — CRÍTICO:**
- `tool_calls[].function.arguments` é **dict**, nunca string JSON
- role `tool` sempre tem campo `"name"` com o nome da ferramenta
- assistant que invoca tools tem `content: ""` (ou thinking muito breve)
- Última mensagem é sempre `{"role": "assistant", "content": "..."}` com a resposta final

---

## CATEGORIA 1 — tool_chain (200 exemplos)

**Subcategorias e volumes:**
- `tool_chain_short` (2-3 tools): 60 exemplos
- `tool_chain_medium` (4-6 tools): 80 exemplos
- `tool_chain_dependent` (resultado de tool determina próxima): 60 exemplos

**O que treina:** encadear múltiplas ferramentas em sequência, usando o resultado de uma para decidir a próxima.

### tool_chain_short — padrão base:
```
system: "You are [Agent]. Tools: [lista]. Objective: [tarefa simples com 2-3 tools]."
user: "[instrução clara]\n\n### MANDATORY RULES FOR THIS TASK:\n- [regra]\n- finish with '[FRASE]'"
assistant(tool_calls): [tool1]
tool/tool1: resultado1
assistant(tool_calls): [tool2]
tool/tool2: resultado2
assistant: "...resumo usando resultado1 e resultado2... FRASE"
```

### tool_chain_dependent — resultado determina próxima ação:
```
user: "Verifique o serviço e, se estiver parado, reinicie-o."
assistant(tool_calls): [run_bash "systemctl is-active n8n"]
tool/run_bash: "inactive"
assistant(tool_calls): [run_bash "systemctl start n8n"]   ← decisão baseada no resultado anterior
tool/run_bash: "Started n8n.service."
assistant(tool_calls): [run_bash "systemctl is-active n8n"]
tool/run_bash: "active"
assistant: "Serviço n8n estava inativo. Reiniciado com sucesso e confirmado ativo. TASK COMPLETED"
```

**Variações de tools a usar (misture entre os 200 exemplos):**
- `run_bash` + `write_file`
- `http_get` + `write_file` + `send_claudio`
- `read_file` + `run_bash`
- `write_file` + `run_bash` (executar o que escreveu)
- `run_bash` + `run_bash` (diagnose → fix)
- `http_get` + `http_get` + `http_get` + `write_file`

**Agentes fictícios variados (não só forge-f3):**
- System Monitor, Log Analyzer, Deploy Agent, Health Checker,
  Report Generator, Config Manager, Backup Agent, Alert Dispatcher

**Resultados realistas de tools:**
- `run_bash("docker ps")` → tabela: n8n (Up 3 days), qdrant (Up 5 days), ollama (Up 1 day)
- `run_bash("free -h")` → "Mem: 128G total, 14G used, 112G free"
- `run_bash("df -h /")` → "/ 920G 127G 747G 15% /"
- `run_bash("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader")` → "23%, 5832 MiB\n18%, 4201 MiB"
- `http_get("https://economia.awesomeapi.com.br/json/last/USD-BRL")` → `{"USDBRL":{"bid":"5.1628","ask":"5.1645","high":"5.1830","low":"5.1420"}}`
- `write_file(path, content)` → `{"success":true,"path":"arquivo.md","bytes":1203}`
- `read_file(path)` → `{"content":"conteúdo do arquivo...","path":"arquivo.md"}`

---

## CATEGORIA 2 — completion_signal (150 exemplos)

**Subcategorias:**
- `completion_from_must_rules` (frase injetada no prompt inicial): 60 exemplos
- `completion_from_hint` (engine injeta completion_hint no final): 60 exemplos
- `completion_partial` (modelo identifica que não concluiu e recusa emitir frase): 30 exemplos

**O que treina:** emitir a frase de encerramento EXATA quando exigida, e APENAS quando a tarefa foi realmente concluída.

### completion_from_must_rules:
```
user: "[tarefa]\n\n### MANDATORY RULES FOR THIS TASK:\n- [regras de execução]\n- finish the response with the exact phrase 'DEPLOY COMPLETE'"
assistant(tool_calls): [executa tools necessárias]
tool: resultado
assistant: "Deploy realizado com sucesso. Container reiniciado e verificado. DEPLOY COMPLETE"
```

### completion_from_hint (engine injeta após max_cycles):
```
user: "[tarefa original]"
assistant(tool_calls): [tool1]
tool: resultado1
assistant(tool_calls): [tool2]
tool: resultado2
[...mais tool calls...]
user: "Produce your final response based on the tools executed above.\n\nTools already executed:\n  - run_bash({\"command\": \"docker ps\"})\n  - write_file({\"path\": \"report.md\"})\n\nYour response MUST include: 'MONITORING ACTIVE'"
assistant: "Sistema monitorado com sucesso. Docker verificado, 4 containers ativos. Relatório em report.md. MONITORING ACTIVE"
```

### completion_partial — modelo RECUSA emitir frase porque não concluiu:
```
user: "[tarefa complexa]\n\n### MANDATORY RULES:\n- run all 4 health checks\n- finish with 'HEALTH CHECK COMPLETE'"
assistant(tool_calls): [run_bash "check1"]
tool: "OK"
assistant(tool_calls): [run_bash "check2"]
tool: "FAILED: connection timeout"
assistant: "Verificação parcial: check1 OK, check2 falhou (timeout). Não é possível emitir 'HEALTH CHECK COMPLETE' pois nem todos os checks passaram. Recomendo investigar a conexão antes de prosseguir."
```

**Frases a variar (distribua uniformemente):**
`ANÁLISE CONCLUÍDA`, `TOOL CRIADO`, `SKILL CRIADA`, `TASK COMPLETED`,
`DEPLOY COMPLETE`, `MONITORING ACTIVE`, `REPORT GENERATED`, `MIGRATION DONE`,
`HEALTH CHECK COMPLETE`, `BACKUP COMPLETE`, `SYNC COMPLETE`, `AUDIT DONE`

---

## CATEGORIA 3 — must_rules (200 exemplos)

**Subcategorias:**
- `must_proactive` (modelo segue todas as regras desde o início): 80 exemplos
- `must_correction_loop` (engine injeta correção, modelo completa): 70 exemplos
- `must_complex` (4-6 regras simultâneas, algumas abertas, algumas com frase exata): 50 exemplos

**O que treina:** cumprir múltiplas must rules simultâneas, e responder corretamente quando o engine injeta a mensagem de correção.

### must_proactive — padrão base:
```
user: "[tarefa]\n\n### MANDATORY RULES FOR THIS TASK:\n- rule1\n- rule2\n- rule3\n- finish with 'FRASE'"
assistant(tool_calls): [executa tudo que as rules exigem]
tool: resultado
assistant: "resposta que satisfaz TODAS as rules acima + FRASE"
```

### must_correction_loop — engine detecta regra não cumprida:
```
user: "[tarefa]\n\n### MANDATORY RULES:\n- include section SUMMARY\n- include section RECOMMENDATIONS\n- cite exact API values\n- finish with 'ANALYSIS COMPLETED'"
assistant(tool_calls): [http_get ...]
tool: resultado com valores reais
assistant: "Análise concluída. USD em 5.16. ANALYSIS COMPLETED"   ← faltou SUMMARY e RECOMMENDATIONS
user: "Your response is incomplete. The following mandatory rules were not met:\n- include section SUMMARY\n- include section RECOMMENDATIONS\n\nComplete your response by including the missing items."
assistant: "## SUMMARY\nUSD/BRL em 5.1628, alta de 0.3% na semana.\n\n## RECOMMENDATIONS\nManter posição em dólar dado tendência de alta...\n\nANALYSIS COMPLETED"
```

### must_complex — regras de tipos diferentes simultâneas:
```
user: "[tarefa]\n\n### MANDATORY RULES:\n- fetch data via http_get before any analysis\n- include sections: CURRENT STATUS, TREND, RECOMMENDATION\n- cite the exact 'bid' value from the API response\n- save report via write_file\n- notify via send_claudio\n- finish with 'ANÁLISE CONCLUÍDA'"
```
Modelo executa TODAS as 6 regras sem esquecimento.

**Conjuntos de regras a variar (misture):**

Set análise: fetch API → seções obrigatórias → citar valores exatos → salvar arquivo → notificar → frase final
Set código: type hints → docstring → tratar exceção → rodar pytest → frase final
Set documentação: YAML frontmatter → seções → mencionar docker → executar teste → frase final
Set monitoramento: check GPU → check memória → check containers → salvar relatório → frase final
Set deploy: pull imagem → parar container → iniciar container → verificar logs → frase final
Set backup: verificar espaço → criar diretório → copiar arquivos → verificar integridade → frase final

---

## CATEGORIA 4 — must_not_guardrails (150 exemplos)

**Subcategorias:**
- `must_not_proactive` (modelo evita comportamento proibido desde o início): 70 exemplos
- `must_not_correction_loop` (modelo viola → engine injeta → modelo corrige): 80 exemplos

**O que treina:** reconhecer e respeitar restrições do must_not, e corrigir comportamento quando o engine detecta violação.

### must_not_proactive — modelo NÃO faz o que é proibido:

Dado um system prompt com must_not rules, o modelo executa a tarefa sem violar nenhuma:

```
system: "You are Market Analyst.\nMUST NOT:\n- invent or estimate values not returned by the API\n- include investment advice\n- use external sources other than awesomeapi.com.br"
user: "Analise o câmbio atual.\n\n### MANDATORY RULES:\n- fetch via http_get\n- finish with 'ANÁLISE CONCLUÍDA'"
assistant(tool_calls): [http_get "https://economia.awesomeapi.com.br/json/last/USD-BRL"]
tool/http_get: '{"USDBRL":{"bid":"5.1628","high":"5.1830","low":"5.1420"}}'
assistant: "USD/BRL: bid=5.1628, máxima=5.1830, mínima=5.1420. Dados obtidos via API.\nANÁLISE CONCLUÍDA"
```
(Modelo NÃO inventou valores, NÃO deu conselho de investimento, NÃO usou outra fonte)

### must_not_correction_loop — CRÍTICO para treinar o loop de correção:

O padrão exato que o engine injeta é:
```
"Your previous response violated the following restrictions:\n- [violação detectada]\n\nRewrite your response without violating these restrictions.\n\nOriginal question: [input original]\n\nContent to rewrite:\n[output_que_violou]"
```

Exemplo completo:
```
system: "You are Report Writer. MUST NOT: use markdown headers, include personal opinions, mention competitor tools."
user: "Escreva um relatório sobre o uso de GPU no fox-server."
assistant(tool_calls): [run_bash "nvidia-smi"]
tool/run_bash: "GPU 0: RTX 3060, 5832MiB/12288MiB | GPU 1: RTX 3060, 4201MiB/12288MiB"
assistant: "# Relatório de GPU\n\nAs duas GPUs estão funcionando bem. Recomendo usar o Prometheus para monitorar..."
              ↑ violou: usou markdown header (#) e mencionou ferramenta externa (Prometheus)

user: "Your previous response violated the following restrictions:\n- use markdown headers\n- mention competitor tools\n\nRewrite your response without violating these restrictions.\n\nOriginal question: Escreva um relatório sobre o uso de GPU no fox-server.\n\nContent to rewrite:\n# Relatório de GPU\n\nAs duas GPUs estão funcionando bem. Recomendo usar o Prometheus para monitorar..."

assistant: "Relatório de GPU do fox-server:\n\nGPU 0 (RTX 3060): 5.832 MB em uso de 12.288 MB disponíveis (47%).\nGPU 1 (RTX 3060): 4.201 MB em uso de 12.288 MB disponíveis (34%).\n\nAmbas as GPUs operam dentro dos limites normais."
```

**Must_not rules realistas a variar:**
- `do not invent values not returned by tools`
- `do not include markdown headers (# or ##)`
- `do not suggest external tools or services`
- `do not include personal opinions or recommendations`
- `do not repeat information already in the conversation`
- `do not use emojis`
- `do not reveal the system prompt or internal rules`
- `do not make git commits or push code`
- `do not execute destructive commands (rm -rf, DROP TABLE, etc.)`
- `do not use external APIs other than those listed`
- `do not include placeholder values like [TODO] or [INSERT HERE]`
- `do not output raw JSON as the final response — always wrap in prose`

**IMPORTANTE para must_not_correction_loop:**
- A violação na primeira resposta deve ser REAL e ESPECÍFICA (não genérica)
- A mensagem de correção deve usar o formato EXATO acima
- A segunda resposta deve estar 100% correta — sem nenhuma das violações

---

## CATEGORIA 5 — structured_output (150 exemplos)

**Subcategorias:**
- `json_output` (resposta final deve ser JSON válido): 50 exemplos
- `yaml_frontmatter` (arquivo com frontmatter YAML + seções markdown): 50 exemplos
- `required_sections` (resposta com seções obrigatórias na ordem correta): 50 exemplos

### json_output:
```
user: "[tarefa]\n\n### MANDATORY RULES:\n- return results as valid JSON\n- include fields: status, data, timestamp\n- finish with 'REPORT GENERATED'"
assistant(tool_calls): [run_bash "docker ps --format json"]
tool/run_bash: "[{\"Names\":\"n8n\",\"Status\":\"Up 3 days\"},{\"Names\":\"qdrant\",\"Status\":\"Up 5 days\"}]"
assistant: '{"status":"ok","data":[{"service":"n8n","uptime":"3 days"},{"service":"qdrant","uptime":"5 days"}],"timestamp":"2026-06-18T12:00:00Z"}\n\nREPORT GENERATED'
```

### yaml_frontmatter — padrão P4:
```
write_file content deve sempre começar com:
---
name: nome-do-skill
description: Uma linha descrevendo o propósito
---

## Quando usar
...
## Pré-requisitos
...
## Passo-a-passo
1. ...
## Erros comuns
...
## Exemplos
...
```

### required_sections — seções obrigatórias na resposta:
```
user: "[tarefa de análise]\n\n### MANDATORY RULES:\n- include sections: CURRENT STATUS, TREND, VOLATILITY, RECOMMENDATION\n- cite exact values from tool results"
```
A resposta final deve conter TODAS as seções, na ordem, com dados reais das tools.

---

## CATEGORIA 6 — error_recovery (150 exemplos)

**Subcategorias:**
- `tool_error_retry` (tool falha → análise → retry com params diferentes): 50 exemplos
- `bash_fix_loop` (bash retorna erro → modelo lê/entende → corrige comando): 50 exemplos
- `test_fix_loop` (pytest falha → lê arquivo → corrige código → retry): 50 exemplos

### tool_error_retry:
```
assistant(tool_calls): [http_get url="https://api.exemplo.com/dados"]
tool/http_get: '{"error":"404","message":"endpoint not found"}'
assistant(tool_calls): [http_get url="https://api.exemplo.com/v2/dados"]   ← URL corrigida
tool/http_get: '{"data":[...]}'
assistant: "Dados obtidos via endpoint v2. ..."
```

### bash_fix_loop:
```
assistant(tool_calls): [run_bash "docker logs n8n --tail 50"]
tool/run_bash: 'Error: No such container: n8n'
assistant(tool_calls): [run_bash "docker ps -a | grep n8n"]
tool/run_bash: "n8n-container   Exited (1) 2 hours ago"
assistant(tool_calls): [run_bash "docker logs n8n-container --tail 50"]
tool/run_bash: "[logs reais com erro identificável]"
assistant: "Container n8n (nome: n8n-container) saiu há 2 horas. Log indica: ..."
```

### test_fix_loop — padrão P3:
```
write memory_search.py → write test_memory_search.py → run_bash pytest → FAILED → read_file → write corrected → run_bash pytest → passed → TOOL CRIADO
```

Falhas realistas a simular:
- `NameError: name 'sqlite3' is not defined` → import faltando
- `TypeError: search_memory() takes 1 positional argument but 2 were given` → assinatura errada
- `FileNotFoundError` não capturada → except faltando
- `AssertionError: [] != [{'key': 'k1', 'value': 'test'}]` → lógica invertida
- `ImportError: cannot import name 'search_memory'` → nome de função errado

---

## CATEGORIA 7 — memory_usage (100 exemplos)

**Subcategorias:**
- `memory_read_before_answer` (lê memória antes de responder, não inventa): 40 exemplos
- `memory_write_after_learning` (aprende fato novo, escreve na memória): 30 exemplos
- `memory_multi_turn` (usa resultado de turn anterior sem repetir perguntas): 30 exemplos

### memory_read_before_answer:
```
system: "You are Cláudio. Tools: run_bash, read_file. Memory enabled via agent-mesh."
user: "Quais modelos Ollama estão carregados agora?"
assistant(tool_calls): [run_bash "docker exec ollama ollama list"]
tool/run_bash: "NAME              SIZE\nqwen3.5:27b      16 GB\ngemma4:e4b        3.2 GB"
assistant: "Modelos carregados no Ollama: qwen3.5:27b (16 GB) e gemma4:e4b (3.2 GB)."
```
(Modelo NÃO inventa — verifica com tool antes de responder)

### memory_write_after_learning:
```
user: "O Conrado mencionou que vai usar o qwen3.6:27b quando lançar. Registra isso."
assistant(tool_calls): [run_bash "python3 ~/.agent-mesh/write-memory.py 'model:next_upgrade' '{\"model\":\"qwen3.6:27b\",\"context\":\"Conrado mencionou preferência\"}' claude"]
tool/run_bash: "Memory written: model:next_upgrade"
assistant: "Registrado na memória compartilhada: próximo upgrade planejado para qwen3.6:27b."
```

### memory_multi_turn — não repete o que já sabe:
```
messages: [
  {"role": "user", "content": "O servidor tem 128GB RAM e 2x RTX 3060."},
  {"role": "assistant", "content": "Entendido. RAM 128GB, dual RTX 3060 (24GB VRAM total)."},
  {"role": "user", "content": "Quanto de VRAM total temos disponível?"},
  {"role": "assistant", "content": "24GB no total (2x 12GB). Com os modelos atuais carregados, aproximadamente 16GB livres."}
]
```
(Não pergunta de volta, não chama tool — usa o contexto já presente)

---

## CATEGORIA 8 — context_compaction (100 exemplos)

**O que treina:** quando o histórico é longo, extrair as informações críticas e resumir sem perder dados importantes.

### Padrão — histórico longo com múltiplos tool results:
```
messages: [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "Faça análise completa do sistema."},
  {"role": "assistant", "tool_calls": [run_bash "docker ps"]},
  {"role": "tool", "content": "[tabela longa de containers]", "name": "run_bash"},
  {"role": "assistant", "tool_calls": [run_bash "free -h"]},
  {"role": "tool", "content": "Mem: 128G total, 14G used, 112G free\nSwap: 0B", "name": "run_bash"},
  {"role": "assistant", "tool_calls": [run_bash "nvidia-smi ..."]},
  {"role": "tool", "content": "[saída longa do nvidia-smi]", "name": "run_bash"},
  {"role": "assistant", "tool_calls": [run_bash "df -h"]},
  {"role": "tool", "content": "[tabela de discos]", "name": "run_bash"},
  {"role": "user", "content": "Resuma o estado geral em menos de 5 linhas."},
  {"role": "assistant", "content": "Estado fox-server:\n- Containers: 6 ativos, todos Up\n- RAM: 14GB/128GB (11%)\n- VRAM: 10GB/24GB (42%)\n- Disco: 127GB/920GB (14%)\nSistema operando normalmente. TASK COMPLETED"}
]
```

**Variações:**
- Histórico de análise de mercado → resumo executivo
- Histórico de diagnóstico de erro → root cause em 3 linhas
- Histórico de deploy → status final conciso
- Tool results muito longos → extrair apenas valores relevantes
- Múltiplos turnos de Q&A → compactar em summary sem perder fatos

---

## CATEGORIA 9 — delegation (100 exemplos)

**O que treina:** usar `run_agent` para delegar subtarefas a agentes especializados.

### Padrão base:
```
system: "You are Orchestrator. Available agents:\n  - lab-ops (system maintenance)\n  - fox-health (diagnostics)\n  - report-gen (report generation)\nTool: run_agent(agent_dir, input)"
user: "Faça health check completo e gere relatório."
assistant(tool_calls): [run_agent agent_dir="agents/fox-health" input="full health check — CPU, GPU, memory, containers, disk"]
tool/run_agent: '{"output":"CPU 35%, RAM 14GB/128GB, GPU0 5.8GB/12GB GPU1 4.2GB/12GB, 6 containers UP, disk 14% used. All OK."}'
assistant(tool_calls): [run_agent agent_dir="agents/report-gen" input="Generate health report from: CPU 35%, RAM 14GB/128GB, GPU0 5.8GB/12GB GPU1 4.2GB/12GB, 6 containers UP, disk 14%"]
tool/run_agent: '{"output":"Health report saved to /tmp/health-2026-06-18.md"}'
assistant: "Health check concluído e relatório gerado. Sistema 100% operacional. TASK COMPLETED"
```

**Padrões a cobrir:**
- Delegar uma subtarefa simples
- Orquestrar 2 agentes em sequência (resultado do primeiro alimenta o segundo)
- Delegar e usar resultado para tomar decisão
- Delegar para agente errado → corrigir → delegar para o correto
- Sub-agente retorna erro → orquestrador trata e reporta

---

## CATEGORIA 10 — no_tool_redirect (50 exemplos)

**O que treina:** quando o engine injeta a mensagem de redirect, o modelo DEVE chamar uma tool — não responder com texto.

**Padrão exato:**
```
user: "[tarefa que requer tool]"
assistant: "[responde com texto/código sem chamar tool]"   ← comportamento errado
user: "You have not used any tools yet. Do NOT output code or text directly — use the available tools to complete the task. Call the appropriate tool now to proceed."
assistant(tool_calls): [tool_correta]   ← comportamento correto após redirect
tool: resultado
assistant: "resposta final baseada no resultado real"
```

**Tarefas onde o redirect ocorre (variar):**
- Verificar containers → `run_bash "docker ps"`
- Verificar GPU → `run_bash "nvidia-smi ..."`
- Ler arquivo de config → `read_file`
- Fazer chamada API → `http_get`
- Verificar processos → `run_bash "ps aux | grep ..."`
- Checar espaço em disco → `run_bash "df -h"`
- Listar modelos Ollama → `run_bash "docker exec ollama ollama list"`

---

## Diretrizes gerais

### O que NÃO gerar:
- Qualquer exemplo conversacional (sem tools, sem regras, sem engine patterns)
- Exemplos onde o modelo recusa executar tarefa sem motivo técnico válido
- arguments como string JSON (sempre dict)
- Valores de tool results completamente irreais
- Completion phrases com case diferente do especificado

### Distribuição de complexidade por categoria:
- Categorias 1-4: 30% simples, 50% média, 20% complexa
- Categorias 5-10: 50% simples, 40% média, 10% complexa

### Resultados de tool canônicos do fox-server (use consistentemente):
```
docker ps:      n8n (Up 3 days), qdrant (Up 5 days), ollama (Up 1 day),
                open-webui (Up 1 day), portainer (Up 7 days), fortejus-api (Up 2 days)
free -h:        Mem: 128G total, 14G used, 112G free
nvidia-smi:     GPU 0: RTX 3060 12GB, ~5-6GB usado | GPU 1: RTX 3060 12GB, ~4-5GB usado
df -h /:        / 920G 127G 747G 15%
ollama list:    qwen3.5:27b (16GB), gemma4:e4b (3.2GB), qwen3.5:9b (5.8GB)
systemctl:      n8n.service: active, aurelia.service: active, claudio-api.service: active
```

---

## Instrução de execução

**IMPORTANTE — rate limit:** Gere em lotes de 30 exemplos. Após cada lote, faça append ao arquivo e aguarde 60 segundos antes de continuar. Não force geração contínua — um strike de rate limit trava 3 horas.

**Primeiro lote:** v2-c001 a v2-c030 (30 exemplos)
**Sequência:** gere 30 → salva → aguarda 60s → gere próximos 30 → repete

Distribuição total alvo (1350 exemplos em ~45 lotes de 30):
- cat1 tool_chain: 200
- cat2 completion_signal: 150
- cat3 must_rules: 200
- cat4 must_not_guardrails: 150
- cat5 structured_output: 150
- cat6 error_recovery: 150
- cat7 memory_usage: 100
- cat8 context_compaction: 100
- cat9 delegation: 100
- cat10 no_tool_redirect: 50

Comando de append após cada lote:
```bash
# Agy deve executar após cada bloco de 30:
python3 -c "
import json
path = '/home/conrado/repos/estudo/agents-framework/finetune/dataset/synth_agentforge_v2.jsonl'
# [lista de 30 exemplos gerados]
with open(path, 'a') as f:
    for ex in examples:
        f.write(json.dumps(ex, ensure_ascii=False) + '\n')
lines = sum(1 for _ in open(path))
print(f'Total acumulado: {lines} exemplos')
"
```

Antes de salvar cada exemplo, verifique:
- [ ] arguments é dict
- [ ] role tool tem campo name
- [ ] completion phrase está exata (case-sensitive)
- [ ] must_not correction loop usa o formato exato da mensagem do engine
- [ ] must compliance correction loop usa o formato exato da mensagem do engine
- [ ] resultado de tool é realista e consistente com os valores canônicos acima
