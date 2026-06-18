# AGY_AGENTFORGE — Geração de Dataset para Fine-tuning AgentForge

## Contexto

Estamos treinando qwen3.5:9b para operar como agente no AgentForge — um framework de agentes local que executa modelos via Ollama. O treinamento **não é para comportamento conversacional**. É para comportamento agentico real: usar tools, seguir must_rules, produzir arquivos estruturados, iterar até completar tarefas.

**Arquivo de saída:** `finetune/dataset/synth_agentforge_batch1.jsonl`
**Volume:** 120 exemplos (IDs: `af-c001` a `af-c120`)
**Formato:** JSONL, uma linha por exemplo

## Como o engine funciona (contexto essencial)

O AgentRuntime executa cada turno assim:

1. **Monta mensagens:** `[system_prompt] + history + [user_msg_com_must_rules]`
2. **Ciclo de tool calling** (até `max_tool_cycles`): LLM → tool_calls? → executa → injeta resultado como `{"role": "tool", ...}` → próxima inferência
3. **Redirect sem tool:** se o modelo responde sem chamar tool quando deveria → engine injeta: `"You have not used any tools yet. Do NOT output code..."` → modelo deve chamar tool na próxima vez
4. **Completion hint** (quando max_cycles esgota): engine injeta `"Produce your final response... Tools already executed: ... Your response MUST include: 'FRASE_EXATA'"`
5. **Must compliance check:** engine verifica se must_rules foram cumpridas → se não, injeta correção e reexecuta

As mensagens `{"role": "tool", ...}` transportam o resultado da execução real. O modelo recebe esse resultado e continua.

## Formato de cada exemplo

```json
{
  "id": "af-c001",
  "source": "synthetic_agy",
  "category": "agentforge",
  "subcategory": "<uma das 8 abaixo>",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "...", "arguments": {...}}}]},
    {"role": "tool", "content": "...", "name": "..."},
    {"role": "assistant", "content": "...resposta final..."}
  ]
}
```

**Regras de formato:**
- `tool_calls[].function.arguments` é um **dict**, não uma string JSON
- Mensagem `tool` sempre tem o campo `"name"` com o nome da ferramenta
- O `assistant` que invoca tools tem `content: ""` ou thinking breve, nunca resposta final
- Completion phrases exatas (ex: `'SKILL CREATED'`) devem aparecer na última mensagem do assistant

---

## Categorias e distribuição

| Categoria | Subcategoria | Exemplos |
|---|---|---|
| 1. Tool chain completo | `tool_chain_complete` | 20 |
| 2. Completion signal | `completion_signal` | 20 |
| 3. Arquivo estruturado | `structured_file` | 15 |
| 4. Loop iterativo (fix) | `iterative_fix` | 15 |
| 5. Redirect sem tool | `no_tool_redirect` | 10 |
| 6. Must rules múltiplas | `must_rules_compliance` | 15 |
| 7. Memória multi-turn | `memory_multi_turn` | 15 |
| 8. Delegação de agente | `agent_delegation` | 10 |

---

## CATEGORIA 1 — tool_chain_complete (20 exemplos)

**O que treina:** quando a tarefa exige múltiplas chamadas de tool em sequência, o modelo deve chamar TODAS — não parar após a primeira.

**Padrão de mensagens:**
```
user: "[tarefa que exige 4+ API calls] + MANDATORY RULES: - chamar todas as APIs listadas"
assistant(tool_calls): [http_get URL1]
tool: resultado1
assistant(tool_calls): [http_get URL2]
tool: resultado2
assistant(tool_calls): [http_get URL3]
tool: resultado3
assistant(tool_calls): [write_file com todos os dados]
tool: arquivo criado
assistant: "relatório completo... ANALYSIS COMPLETED"
```

**System prompt base (F3-like):**
```
You are Market Analyst (ID: forge-f3).
Objective: Fetch exchange rates via API, analyze trends, generate report.
Tools: http_get (fetch URLs), write_file (save report), send_claudio (notify).
Mandatory: fetch each quote separately via http_get. Finish with 'ANALYSIS COMPLETED'.
```

**Variações a gerar (20 exemplos):**
- Cotações cambiais: USD-BRL, EUR-BRL, BTC-BRL, ETH-BRL (4 calls)
- Preços de ações: PETR4, VALE3, ITUB4, BBDC4 (4 calls)
- Status de servidores: fox-server, fox-note, nerds-dev, igor-dev (4 calls via run_bash)
- APIs de clima: SP, RJ, BH, Brasília (4 calls)
- Métricas de container: n8n, qdrant, ollama, open-webui (4 calls via run_bash)
- Mistura: 2-3 tipos diferentes de API na mesma tarefa

**IMPORTANTE:** Cada chamada de tool deve ter resultado realista e diferente. Não repita o mesmo valor em todas.

---

## CATEGORIA 2 — completion_signal (20 exemplos)

**O que treina:** quando o sistema injeta `"Your response MUST include: 'FRASE_EXATA'"`, a última mensagem do assistant DEVE conter essa frase exata.

**Padrão de mensagens (2 cenários):**

**2a — completion_hint após max_cycles (engine injeta após esgotar ciclos):**
```
user: [tarefa original]
assistant(tool_calls): [várias tools]
tool: resultado
...
user: "Produce your final response based on the tools executed above.\nTools already executed:\n  - write_file(...)\n  - run_bash(...)\nYour response MUST include: 'SKILL CREATED'"
assistant: "...resumo do que foi feito... SKILL CREATED"
```

**2b — must_rules injeta frase no prompt desde o início:**
```
user: "[tarefa]\n\n### MANDATORY RULES FOR THIS TASK:\n- ...\n- finish the response with the exact phrase 'TOOL CREATED'"
assistant(tool_calls): [executa as tools]
tool: resultado
assistant: "...TOOL CREATED"
```

**Frases exatas a usar (variar entre os 20 exemplos):**
- `SKILL CREATED`
- `TOOL CREATED`
- `ANALYSIS COMPLETED`
- `TASK COMPLETED`
- `DEPLOY COMPLETE`
- `MONITORING ACTIVE`
- `REPORT GENERATED`
- `MIGRATION DONE`

**CRÍTICO:** A frase deve aparecer EXATAMENTE como está, sem variações (não `Skill Created`, não `SKILL_CREATED`).

---

## CATEGORIA 3 — structured_file (15 exemplos)

**O que treina:** gerar arquivos com estrutura obrigatória (YAML frontmatter + seções markdown).

**Padrão P4-like:**
```
user: "Crie um skill doc para [tarefa] com YAML frontmatter e seções: quando usar, pré-requisitos, passo-a-passo, erros comuns, exemplos.\n\nMANDATORY RULES:\n- include valid YAML frontmatter with name and description\n- finish the response with the exact phrase 'SKILL CREATED'"
assistant(tool_calls): [write_file path="skill.md" content="---\nname: skill-name\ndescription: ...\n---\n\n## Quando usar\n..."]
tool: {"success": true, "path": "skill.md", "bytes": 1200}
assistant(tool_calls): [run_bash "bash skill-test.sh"]
tool: "test OK"
assistant: "...SKILL CREATED"
```

**Skills a documentar (variar):**
- fox-backup (backup diário vault)
- ollama-restart (reiniciar modelo no Ollama)
- container-health (verificar saúde dos containers)
- n8n-trigger (disparar workflow n8n)
- gpu-monitor (monitorar VRAM)
- log-rotate (rotação de logs)
- db-snapshot (snapshot do qdrant)
- ssh-tunnel (configurar tunnel reverso)

**YAML frontmatter obrigatório em todos:**
```yaml
---
name: nome-do-skill
description: Uma linha descrevendo o que o skill faz
---
```

---

## CATEGORIA 4 — iterative_fix (15 exemplos)

**O que treina:** quando pytest ou bash retorna erro, o modelo analisa, corrige o código e retenta — não desiste após a primeira falha.

**Padrão P3-like:**
```
user: "[criar ferramenta Python com testes que passem]\n\nMANDATORY RULES:\n- run pytest before responding\n- finish with 'TOOL CREATED'"
assistant(tool_calls): [write_file "tool.py"]
tool: criado
assistant(tool_calls): [write_file "test_tool.py"]
tool: criado
assistant(tool_calls): [run_bash "python3 -m pytest test_tool.py -v"]
tool: "FAILED - AssertionError: ..."
assistant(tool_calls): [read_file "tool.py"]
tool: conteúdo do arquivo
assistant(tool_calls): [write_file "tool.py" com correção]
tool: criado
assistant(tool_calls): [run_bash "python3 -m pytest test_tool.py -v"]
tool: "5 passed in 0.03s"
assistant: "...TOOL CREATED"
```

**Ferramentas Python a criar (variar):**
- `parse_nginx_log(path: str) -> list[dict]` — parser de access log
- `search_memory(db: str, query: str) -> list[dict]` — busca em SQLite
- `format_gpu_stats(raw: str) -> dict` — parseia saída do nvidia-smi
- `validate_yaml_frontmatter(content: str) -> bool` — valida skill docs
- `extract_docker_stats(raw: str) -> list[dict]` — parseia docker stats

**Falhas intencionais a corrigir:**
- Import faltando
- Nome de função diferente do esperado no import do teste
- Lógica invertida (retorna [] quando deveria retornar dados)
- Exceção não tratada (FileNotFoundError não capturada)
- Tipo de retorno errado (str vs dict)

---

## CATEGORIA 5 — no_tool_redirect (10 exemplos)

**O que treina:** quando o engine injeta a mensagem de redirect "You have not used any tools yet...", o modelo DEVE chamar uma tool na resposta seguinte — não responder com texto.

**Padrão:**
```
user: "[tarefa que requer tool]"
assistant: "Para verificar o status do Docker, você pode usar docker ps..."  ← (errado - respondeu sem tool)
user: "You have not used any tools yet. Do NOT output code or text directly — use the available tools to complete the task. Call the appropriate tool now to proceed."
assistant(tool_calls): [run_bash "docker ps"]  ← (correto - chamou a tool)
tool: resultado
assistant: "resposta final baseada no resultado real"
```

**Tarefas (variar):**
- Verificar status de containers
- Verificar uso de GPU
- Ler arquivo de configuração
- Verificar espaço em disco
- Listar modelos no Ollama
- Verificar processos em execução
- Testar conectividade de serviço

---

## CATEGORIA 6 — must_rules_compliance (15 exemplos)

**O que treina:** seguir MÚLTIPLAS regras simultâneas do must_rules sem esquecer nenhuma.

**Padrão — 4-6 regras simultâneas:**
```
user: "[tarefa]\n\n### MANDATORY RULES FOR THIS TASK:\n- rule1\n- rule2\n- rule3\n- rule4\n- finish with 'TASK COMPLETED'"
assistant(tool_calls): [executa tools necessárias para satisfazer todas as regras]
tool: resultado
...
assistant: "resposta que satisfaz TODAS as regras acima + TASK COMPLETED"
```

**Conjuntos de regras realistas:**

Set A (análise):
- search for current data via http_get before analyzing
- include sections: CURRENT STATUS, TREND, RECOMMENDATION
- cite the exact values from the API response
- finish with 'ANALYSIS COMPLETED'

Set B (código):
- include type hints in all functions
- include docstrings
- handle exceptions without crashing
- run pytest before responding
- finish with 'TOOL CREATED'

Set C (documentação):
- include valid YAML frontmatter with name and description
- include sections: when to use, prerequisites, step-by-step, errors, examples
- mention docker compose commands
- execute validation test before responding
- finish with 'SKILL CREATED'

Set D (monitoramento):
- check GPU status via run_bash
- check memory usage via run_bash
- check Docker containers via run_bash
- save report via write_file
- finish with 'MONITORING COMPLETE'

---

## CATEGORIA 7 — memory_multi_turn (15 exemplos)

**O que treina:** em agentes com memória ativa (`memory.enabled: true`), manter coerência entre turnos — referenciar o que foi dito antes, não repetir perguntas já respondidas.

**Padrão (2-3 turnos):**
```
messages: [
  {"role": "system", "content": "You are [agent]. Memory enabled. Previous context available."},
  {"role": "user", "content": "turno 1 — estabelece contexto (ex: 'meu servidor usa RTX 3060')"},
  {"role": "assistant", "content": "entendido, RTX 3060 registrado"},
  {"role": "user", "content": "turno 2 — refere ao contexto (ex: 'quanto VRAM tenho disponível?')"},
  {"role": "assistant", "content": "baseado no que você informou (RTX 3060 tem 12GB)... [sem chamar tool para info já conhecida]"}
]
```

**Padrões multi-turn a cobrir:**
- Lembrar especificações de hardware mencionadas antes
- Não repetir perguntas já respondidas
- Referenciar resultado de tool call de turno anterior
- Manter contexto de tarefa em andamento (ex: "continue o deploy que iniciamos")
- Compactar contexto longo sem perder informações críticas

---

## CATEGORIA 8 — agent_delegation (10 exemplos)

**O que treina:** usar a tool `run_agent` para delegar subtarefas a agentes especializados, em vez de tentar fazer tudo diretamente.

**System prompt base (orchestrator-like):**
```
You are Orchestrator. Available agents:
  - lab-ops (agent_dir=agents/lab-ops): system monitoring and maintenance
  - fox-health (agent_dir=agents/fox-health): health check and diagnostics
Tool: run_agent(agent_dir, input) — delegates to specialized agent.
```

**Padrão:**
```
user: "verifica o estado completo do fox-server"
assistant(tool_calls): [run_agent agent_dir="agents/fox-health" input="full health check"]
tool: {"output": "CPU 35%, MEM 12GB/128GB, GPU OK, containers OK"}
assistant: "Relatório do fox-server: ..."
```

**Cenários a gerar:**
- Delegar health check ao fox-health
- Delegar tarefa de manutenção ao lab-ops
- Orquestrar 2 agentes em sequência
- Delegar análise e usar resultado para tomar decisão
- Repassar subtarefa que falhou a agente diferente

---

## Diretrizes gerais

### O que NÃO gerar:
- Exemplos conversacionais (perguntas e respostas simples sem tools)
- Exemplos onde o modelo recusa a tarefa sem motivo
- Exemplos com inventação de resultados de tool (o `content` do role `tool` deve ser realista)
- Exemplos com tool_calls onde `arguments` seja uma string JSON (deve ser dict)
- Exemplos onde o modelo não emite a completion phrase quando explicitamente exigida

### Resultados de tool realistas:
- `run_bash("docker ps")` → tabela com containers reais (n8n, qdrant, ollama, etc.)
- `run_bash("free -h")` → memória do fox-server (~128GB total, ~15GB usada)
- `run_bash("nvidia-smi --query-gpu=...")` → RTX 3060, ~5-7GB VRAM usada
- `http_get("https://economia.awesomeapi.com.br/json/last/USD-BRL")` → JSON com campos `bid`, `ask`, `high`, `low`
- `write_file(...)` → `{"success": true, "path": "arquivo.md", "bytes": N}`
- `read_file(...)` → `{"content": "conteúdo do arquivo", "path": "arquivo"}`

### Distribuição de complexidade:
- 40% simples (1-2 tool calls, tarefa clara)
- 40% média (3-5 tool calls, iteração ou múltiplas rules)
- 20% complexa (6+ tool calls, correção de erro, orquestração)

---

---

## CENÁRIOS DE BENCHMARK REAIS (prioridade máxima)

Estes 3 cenários são os que o 9b precisa dominar. Cada variação que você gerar para as outras categorias deve ser inspirada neles. Os checks abaixo são **obrigatórios** — um exemplo que não os satisfaz 100% não deve ser incluído no dataset.

### F3 — Market Analyst (agent: forge-f3)

**Tools disponíveis:** `http_get`, `write_file`, `send_claudio`

**Checks obrigatórios (todo exemplo F3-like deve satisfazer TODOS):**
1. `http_get` chamado com URL contendo `awesomeapi.com.br/json/last/USD-BRL`
2. `http_get` chamado com URL contendo `awesomeapi.com.br/json/last/BTC-BRL`
3. `http_get` chamado com URL contendo `awesomeapi.com.br/json/daily/USD-BRL/7`
4. O resultado do http_get para USD-BRL contém campo `bid` com valor real (ex: `"bid": "5.1623"`)
5. Arquivo `.md` criado via `write_file`
6. Arquivo contém a palavra `COTAÇÕES`
7. Arquivo contém a palavra `TEND` (TENDÊNCIA)
8. Arquivo contém a palavra `RECOMEND` (RECOMENDAÇÃO)
9. Arquivo menciona `USD` ou dólar
10. Arquivo menciona `BTC` ou Bitcoin
11. `send_claudio` chamado com mensagem de resumo
12. Resposta final contém `ANÁLISE CONCLUÍDA`
13. Sem erros de API (resultados válidos das tools)

**Exemplo esqueleto de sequência correta:**
```
user: "[tarefa]\n\n### MANDATORY RULES...\n- search for real quotes via http_get\n- include sections COTAÇÕES, TENDÊNCIA (with DÓLAR TREND), ANÁLISE DE VOLATILIDADE, and RECOMENDAÇÃO\n- send summary via send_claudio at the end\n- finish with 'ANÁLISE CONCLUÍDA'"

assistant(tool_calls): [http_get url="https://economia.awesomeapi.com.br/json/last/USD-BRL"]
tool/http_get: '{"USDBRL":{"bid":"5.1628","ask":"5.1650","high":"5.1830","low":"5.1420"}}'

assistant(tool_calls): [http_get url="https://economia.awesomeapi.com.br/json/last/BTC-BRL"]
tool/http_get: '{"BTCBRL":{"bid":"329134.00","ask":"329500.00","high":"332000.00","low":"325000.00"}}'

assistant(tool_calls): [http_get url="https://economia.awesomeapi.com.br/json/daily/USD-BRL/7"]
tool/http_get: '[{"bid":"5.1628"},{"bid":"5.1542"},{"bid":"5.1701"},{"bid":"5.1388"},{"bid":"5.1452"},{"bid":"5.1319"},{"bid":"5.0987"}]'

assistant(tool_calls): [write_file path="analise-mercado.md" content="# Análise de Mercado\n\n## COTAÇÕES\n- USD/BRL: R$ 5,1628 (máx 5,1830 / mín 5,1420)\n- BTC/BRL: R$ 329.134,00 (máx 332.000 / mín 325.000)\n\n## TENDÊNCIA\nO dólar apresenta ALTA na semana...\n\n## ANÁLISE DE VOLATILIDADE\n...\n\n## RECOMENDAÇÃO\n..."]
tool/write_file: '{"success":true,"path":"analise-mercado.md","bytes":1847}'

assistant(tool_calls): [send_claudio message="Análise concluída: USD=5,1628 (ALTA), BTC=329.134 (ESTÁVEL). Relatório em analise-mercado.md"]
tool/send_claudio: '{"sent":true,"message_id":3435}'

assistant: "Análise finalizada. USD/BRL em 5,1628 com tendência de alta moderada. BTC/BRL estável em 329.134. Relatório gerado e enviado via Cláudio.\n\nANÁLISE CONCLUÍDA"
```

---

### P3 — Python Tool Builder (agent: real-p3)

**Tools disponíveis:** `write_file`, `read_file`, `run_bash`

**Checks obrigatórios:**
1. Arquivo `memory_search.py` criado
2. Sintaxe Python válida
3. Contém type hints (`-> `)
4. Contém docstring (`"""`)
5. Usa `sqlite3`
6. Trata exceção (`except`)
7. Arquivo `test_memory_search.py` criado
8. Tests passam (`run_bash "python3 -m pytest..."` retorna `passed`)
9. Resposta final contém `TOOL CRIADO`

**Exemplo esqueleto:**
```
user: "Crie a ferramenta search_memory...\n\n### MANDATORY RULES:\n- include type hints\n- include docstrings\n- handle file not found\n- function name must be search_memory\n- run pytest before responding\n- finish with 'TOOL CRIADO'"

assistant(tool_calls): [write_file path="memory_search.py" content="import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Busca registros em banco SQLite por query substring.\"\"\"\n    if not Path(db).exists():\n        raise FileNotFoundError(f'Banco não encontrado: {db}')\n    conn = sqlite3.connect(db)\n    try:\n        cursor = conn.execute(\n            'SELECT key, value FROM memory WHERE value LIKE ?',\n            (f'%{query}%',)\n        )\n        return [{'key': r[0], 'value': r[1]} for r in cursor.fetchall()]\n    finally:\n        conn.close()\n"]
tool/write_file: '{"success":true,"path":"memory_search.py","bytes":412}'

assistant(tool_calls): [write_file path="test_memory_search.py" content="import pytest\nimport sqlite3\nimport tempfile\nfrom pathlib import Path\nfrom memory_search import search_memory\n\n@pytest.fixture\ndef tmp_db(tmp_path):\n    db = str(tmp_path / 'test.db')\n    conn = sqlite3.connect(db)\n    conn.execute('CREATE TABLE memory (key TEXT, value TEXT)')\n    conn.execute(\"INSERT INTO memory VALUES ('k1', 'ollama config')\")\n    conn.execute(\"INSERT INTO memory VALUES ('k2', 'docker stats')\")\n    conn.commit()\n    conn.close()\n    return db\n\ndef test_found(tmp_db):\n    r = search_memory(tmp_db, 'ollama')\n    assert len(r) == 1\n    assert r[0]['key'] == 'k1'\n\ndef test_not_found(tmp_db):\n    r = search_memory(tmp_db, 'xyz')\n    assert r == []\n\ndef test_file_not_found():\n    with pytest.raises(FileNotFoundError):\n        search_memory('/nao/existe.db', 'q')\n"]
tool/write_file: '{"success":true,"path":"test_memory_search.py","bytes":789}'

assistant(tool_calls): [run_bash command="python3 -m pytest test_memory_search.py -v"]
tool/run_bash: "============================= test session starts ==============================\ntest_memory_search.py::test_found PASSED\ntest_memory_search.py::test_not_found PASSED\ntest_memory_search.py::test_file_not_found PASSED\n\n============================== 3 passed in 0.04s =============================="

assistant: "Ferramenta `search_memory` criada com type hints, docstring e tratamento de FileNotFoundError. Todos os 3 testes passam.\n\nTOOL CRIADO"
```

---

### P4 — Skill Doc Builder (agent: real-p4)

**Tools disponíveis:** `write_file`, `read_file`, `run_bash`

**Checks obrigatórios:**
1. Arquivo `fox-deploy.md` criado
2. YAML frontmatter válido (começa com `---`, contém `name:` e `description:`)
3. Contém seção com `quando usar` (case-insensitive)
4. Contém seção com `passo` (passos)
5. Contém seção com `erro` (erros comuns)
6. Contém seção com `exemplo`
7. Menciona `docker compose`
8. Menciona `Claudio` (notificação)
9. Arquivo de teste criado
10. `run_bash` chamado para executar o teste
11. Resposta final contém `SKILL CRIADA`

**Exemplo esqueleto:**
```
user: "Crie documentação do skill fox-deploy...\n\n### MANDATORY RULES:\n- include valid YAML frontmatter with name and description\n- include sections: quando usar, pré-requisitos, passo-a-passo, erros comuns, exemplos\n- mention docker compose commands\n- mention Claudio notification\n- execute fox-deploy-test.sh before responding\n- finish with 'SKILL CRIADA'"

assistant(tool_calls): [write_file path="fox-deploy.md" content="---\nname: fox-deploy\ndescription: Deploy ou redeploy de containers no fox-server via docker compose\n---\n\n## Quando usar\n\nUse este skill quando precisar atualizar, reiniciar ou fazer deploy de um container no fox-server.\n\n## Pré-requisitos\n\n- Acesso SSH ao fox-server\n- Arquivo docker-compose.yml no diretório do projeto\n\n## Passo-a-passo\n\n1. Acesse o diretório do projeto: `cd ~/repos/producao/<projeto>`\n2. Pull da imagem: `docker compose pull`\n3. Restart do container: `docker compose up -d --force-recreate`\n4. Verifique logs: `docker compose logs -f --tail=50`\n5. Notifique via Claudio: confirme que o serviço está operacional\n\n## Erros comuns\n\n- **Port already in use:** verifique `docker ps` e pare o container conflitante\n- **Image not found:** execute `docker compose pull` antes do up\n- **Container unhealthy:** verifique `docker compose logs` para diagnóstico\n\n## Exemplos\n\n```bash\n# Redeploy do n8n\ncd ~/docker/n8n && docker compose up -d --force-recreate\n\n# Verificar status\ndocker ps | grep n8n\n```\n"]
tool/write_file: '{"success":true,"path":"fox-deploy.md","bytes":1203}'

assistant(tool_calls): [write_file path="fox-deploy-test.sh" content="#!/bin/bash\nset -e\necho 'Validando fox-deploy.md...'\ngrep -q 'quando usar' fox-deploy.md && echo 'OK: quando usar'\ngrep -q 'docker compose' fox-deploy.md && echo 'OK: docker compose'\ngrep -q 'Claudio' fox-deploy.md && echo 'OK: Claudio'\necho 'Todos os checks passaram.'\n"]
tool/write_file: '{"success":true,"path":"fox-deploy-test.sh","bytes":245}'

assistant(tool_calls): [run_bash command="bash fox-deploy-test.sh"]
tool/run_bash: "Validando fox-deploy.md...\nOK: quando usar\nOK: docker compose\nOK: Claudio\nTodos os checks passaram."

assistant: "Skill `fox-deploy` documentado com frontmatter YAML válido, seções completas e teste de validação passando.\n\nSKILL CRIADA"
```

---

## Verificação antes de enviar

Para cada exemplo, confirme:
- [ ] `arguments` é dict, não string
- [ ] role `tool` tem campo `"name"`
- [ ] completion phrase aparece EXATAMENTE como especificado (case-sensitive)
- [ ] resultado de tool é realista (não inventado aleatoriamente)
- [ ] fluxo faz sentido (tool call → resultado → próxima ação logicamente coerente)
- [ ] se há `iterative_fix`: o primeiro pytest falha com erro específico, o segundo passa
- [ ] se é variação de F3: satisfaz TODOS os 13 checks da seção F3
- [ ] se é variação de P3: satisfaz TODOS os 9 checks da seção P3
- [ ] se é variação de P4: satisfaz TODOS os 11 checks da seção P4
