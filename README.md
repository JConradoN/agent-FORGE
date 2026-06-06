# AgentForge

Framework Python **spec-first** e **local-first** para criação, experimentação e execução de agentes LLM on-premise.

O AgentForge encapsula a tese central validada empiricamente por 4 meses de benchmarks (ABS → LOP → FORGE → REAL):

> **20% é o modelo, 80% é o runtime.**

A qualidade de um agente local depende menos do modelo escolhido e mais de como o runtime gerencia contexto, decisões de tool use, guardrails e avaliação. O framework implementa esses mecanismos de forma explícita, testável e spec-driven.

---

## Índice

- [Diferenciais](#diferenciais)
- [Requisitos e Instalação](#requisitos-e-instalação)
- [Fluxo Básico](#fluxo-básico)
- [Canais de Execução](#canais-de-execução)
- [Tool Calling](#tool-calling)
- [Guardrails Ativos](#guardrails-ativos)
- [Reflexão Autônoma](#reflexão-autônoma)
- [Avaliação e Scoring](#avaliação-e-scoring)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Referência CLI](#referência-cli)
- [Desenvolvimento e Testes](#desenvolvimento-e-testes)

---

## Diferenciais

| Característica | O que significa na prática |
|---|---|
| **Spec-First** | O agente nasce de um `agent.yaml`. Nenhum comportamento existe fora da spec. |
| **Local-First** | Otimizado para Ollama. Sem dependências de APIs externas no caminho crítico. |
| **Tool Calling Model-Driven** | O modelo decide quando chamar ferramentas via protocolo OpenAI/Ollama nativo. |
| **Loop Guard** | Detecta ciclos de tool calling repetidos e interrompe antes de esgotar o orçamento. |
| **Reflexão Autônoma** | N rounds de auto-crítica após o output inicial — melhora qualidade sem intervenção humana. |
| **Guardrails Ativos** | Verifica `must_not` no output usando o próprio modelo como juiz. Retenta automaticamente se violado. |
| **Eval com LLM Judge** | Scoring multidimensional usando Ollama local ou Gemini como avaliador. |
| **4 Canais** | CLI, HTTP (n8n), MCP (Claude Code/Desktop), Telegram — mesma spec, qualquer interface. |
| **Multi-Agente** | Orquestrador delega subtarefas para workers declarados no YAML via `run_agent`. |
| **296 testes** | Cobertura ampla garantindo estabilidade do runtime e contratos de API. |

---

## Requisitos e Instalação

**Requisitos:**
- Python 3.11+
- Ollama instalado e rodando (`docker compose` ou local)
- Modelo recomendado: `qwen3.5:9b` (melhor custo-benefício, ~7 GB VRAM)

```bash
git clone <URL-do-repo>
cd agents-framework
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Fluxo Básico

Todo agente segue três etapas:

### 1. Criar a especificação

```bash
agentforge wizard
```

Gera `agents/<id>/agent.yaml` com persona, ferramentas, memória e guardrails.

### 2. Gerar artefatos

```bash
agentforge generate --path agents/<id>/agent.yaml
```

Produz em `agents/<id>/`:
- `system_prompt.md` — prompt de sistema estruturado
- `runtime.yaml` — parâmetros de execução
- `tools.yaml` — schema de ferramentas
- `eval.yaml` — configuração de avaliação
- `README.md` — documentação técnica do agente

### 3. Executar

```bash
agentforge run --agent-dir agents/lab-ops --input "Como está o servidor?"
```

Saída em JSON (`--mode raw`) ou texto legível (`--mode pretty`).

---

## Canais de Execução

O mesmo agente roda em quatro canais sem alterar a spec:

### CLI (padrão)

```bash
agentforge run --agent-dir agents/lab-ops --input "texto" --mode pretty
```

### HTTP — integração com n8n e automações

```bash
agentforge serve --agent-dir agents/lab-ops --port 8080
```

```http
POST http://localhost:8080/run
Content-Type: application/json
{"input": "estado do servidor"}

GET  http://localhost:8080/health
```

### MCP — ferramentas para Claude Code / Claude Desktop

```bash
agentforge mcp --transport stdio
```

Configure em `.mcp.json` na raiz do projeto:

```json
{
  "mcpServers": {
    "agentforge": {
      "command": "/path/to/.venv/bin/agentforge",
      "args": ["mcp"]
    }
  }
}
```

Ferramentas expostas: `collect_system_health`, `read_log_tail`, `scan_directory`, `run_agent`.

### Telegram

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC..."
agentforge telegram --agent-dir agents/lab-ops
```

O bot recebe mensagens de texto, executa o agente e responde. Mostra "digitando..." durante o processamento e sinaliza no reply se guardrails foram acionados.

---

## Tool Calling

O modo `respond_or_tool` ativa o pipeline de tool calling model-driven:

```yaml
# agent.yaml
workflow:
  mode: respond_or_tool
  max_tool_cycles: 5
```

**Fluxo por ciclo:**
1. Inferência com schema de ferramentas (protocolo OpenAI/Ollama nativo)
2. Modelo decide: resposta direta **ou** chamada de ferramenta
3. Se tool call → executa → injeta resultado → próximo ciclo
4. **Loop guard**: para se o mesmo `(tool, args)` se repetir no mesmo ciclo
5. Ao esgotar `max_tool_cycles` → inferência final com todos os resultados acumulados

**Campos úteis no ToolSpec:**

```yaml
tools:
  - name: collect_system_health
    description: "Coleta métricas de CPU, RAM, disco e GPU"
    when_to_use: "Sempre que o usuário perguntar sobre estado do servidor"
    when_not_to_use: "Não usar para perguntas sobre logs específicos"
```

`when_to_use` e `when_not_to_use` são injetados na descrição da ferramenta — funcionam como dicas de decisão que reduzem chamadas erradas em modelos locais.

---

## Guardrails Ativos

Guardrails são verificados **após** o output ser gerado, antes de retornar ao usuário.

```yaml
# agent.yaml
guardrails:
  must:
    - sempre usar dados reais das ferramentas
    - fornecer recomendações baseadas em evidências
  must_not:
    - inventar métricas
    - acessar arquivos fora do diretório de logs
    - alterar qualquer arquivo do sistema
```

**Comportamento em runtime:**
1. Output gerado (tool calling ou resposta direta)
2. Reflexão autônoma aplicada (se configurada)
3. O modelo analisa o próprio output contra as regras `must_not`
4. Se violação detectada: prompt de correção + re-inferência (até 2 retries)
5. Violações persistentes registradas em `result["metadata"]["guardrail_violations"]`

---

## Orquestração Multi-Agente

Um orquestrador é um agente regular que declara workers em `workflow.agents`. O engine injeta `run_agent` automaticamente no schema de tools — o modelo decide quando e para quem delegar.

```yaml
# agents/orchestrator/agent.yaml
workflow:
  mode: respond_or_tool
  max_tool_cycles: 8
  agents:
    - name: lab-ops
      agent_dir: agents/lab-ops
      description: Monitoramento de saúde do servidor e inspeção de logs
    - name: outro-agente
      agent_dir: agents/outro-agente
      description: Análise de documentos
```

**Fluxo de delegação:**
1. Orquestrador recebe tarefa do usuário
2. Modelo analisa e decide delegar → chama `run_agent(agent_dir=..., input=...)`
3. Engine carrega o worker, executa `runtime.run(input)`, retorna o output
4. Output do worker é injetado no histórico do orquestrador
5. Orquestrador sintetiza todos os resultados em resposta final

Workers só aparecem no schema se declarados — modelo não pode inventar agents fora da spec.

```bash
agentforge run --agent-dir agents/orchestrator --input "Relatório completo do servidor"
```

## Reflexão Autônoma

O agente pode revisar o próprio output antes de retornar:

```yaml
# agent.yaml
workflow:
  mode: respond_or_tool
  reflection_rounds: 2
```

Cada round aplica um prompt de auto-crítica estruturado:
- A resposta está completa e precisa?
- Respeita as restrições do papel?
- Pode ser mais objetiva?

A reflexão é estacionária (sem histórico) e executa N vezes sequencialmente.

---

## Avaliação e Scoring

### Avaliação com dataset

```bash
agentforge eval \
  --agent-dir agents/lab-ops \
  --dataset agents/lab-ops/eval_dataset.yaml
```

Formato do dataset:

```yaml
cases:
  - input: "Como está a saúde do servidor?"
    notes: "deve coletar dados reais antes de responder"
  - input: "Há erros nos últimos logs do sistema?"
    notes: "deve usar read_log_tail"
```

Resultados salvos em `agents/<id>/eval_runs/<timestamp>.jsonl`.

### LLM Judge

Ative scoring automático no `agent.yaml`:

```yaml
eval:
  judge_model: "gemma4:e4b"
  criteria:
    - resposta baseada em dados reais
    - recomendação objetiva e acionável
    - sem invenção de métricas
```

O judge pontua cada critério de 0–100 e calcula score médio. Suporta modelos Ollama locais ou `gemini-*` via API Gemini.

---

## Estrutura do Projeto

```
agents-framework/
├── agents/                   # Diretório de agentes (cada um autocontido)
│   ├── lab-ops/              # Agente de referência — monitoramento de infra
│   │   ├── agent.yaml        # Spec do agente (fonte de verdade)
│   │   ├── system_prompt.md  # Prompt gerado
│   │   ├── runtime.yaml      # Parâmetros de execução
│   │   ├── tools.yaml        # Schema de ferramentas
│   │   ├── eval.yaml         # Config de avaliação
│   │   └── eval_dataset.yaml # Casos de teste
│   └── ...
├── src/agentforge/
│   ├── channels/             # Canais de execução
│   │   ├── http.py           # FastAPI REST (n8n, automações)
│   │   ├── mcp_server.py     # FastMCP (Claude Code/Desktop)
│   │   └── telegram.py       # Bot Telegram (polling async)
│   ├── cli/
│   │   └── main.py           # Todos os comandos CLI
│   ├── core/
│   │   ├── agent_models.py   # AgentSpec e sub-specs (Pydantic)
│   │   └── validation.py     # Carregamento e validação de YAML
│   ├── eval/
│   │   └── judge.py          # LLM Judge (Ollama + Gemini)
│   ├── providers/
│   │   ├── base.py           # ProviderRequest / ProviderResponse
│   │   ├── ollama.py         # Integração Ollama (chat + generate)
│   │   ├── mock.py           # Provider determinístico para testes
│   │   └── registry.py       # Factory de providers
│   ├── runtime/
│   │   ├── engine.py         # AgentRuntime: pipeline completo
│   │   └── memory.py         # Histórico, janela, persistência
│   ├── tools/
│   │   ├── registry.py       # Execução de ferramentas por nome
│   │   ├── system_health.py  # collect_system_health
│   │   ├── read_log_tail.py  # read_log_tail
│   │   ├── vault_scan.py     # scan_directory
│   │   └── vault_extract.py  # extração de arquivos vault
│   ├── generators/
│   │   └── agent_files.py    # Geração de artefatos a partir da spec
│   └── wizard/
│       └── flow.py           # Wizard interativo CLI
├── tests/                    # 291 testes
├── docs/
│   ├── ARCHITECTURE.md       # Referência técnica completa
│   └── BLUEPRINT.md          # Blueprint histórico v1
├── specs/                    # Schemas YAML do framework
├── .mcp.json                 # Config MCP para Claude Code
└── pyproject.toml
```

---

## Referência CLI

| Comando | Descrição |
|---|---|
| `agentforge wizard` | Cria spec interativamente |
| `agentforge generate --path <yaml>` | Gera artefatos a partir da spec |
| `agentforge validate [--root .]` | Valida specs do framework |
| `agentforge validate-agent --path <yaml>` | Valida um agent.yaml |
| `agentforge run --agent-dir <dir> --input <texto>` | Executa o agente |
| `agentforge eval --agent-dir <dir> --dataset <yaml>` | Avalia com dataset |
| `agentforge serve --agent-dir <dir> [--port 8080]` | Sobe API HTTP |
| `agentforge mcp [--transport stdio\|http]` | Inicia servidor MCP |
| `agentforge telegram --agent-dir <dir> [--token <tok>]` | Inicia bot Telegram |

---

## Desenvolvimento e Testes

```bash
# Todos os testes
pytest -q

# Arquivo específico
pytest tests/test_runtime_engine.py -v

# Canal HTTP
pytest tests/test_http_channel.py -v

# Canal Telegram
pytest tests/test_telegram_channel.py -v
```

O projeto usa `MockProvider` (`deployment.provider: mock`) para testes determinísticos — sem Ollama necessário no CI.

Para documentação técnica detalhada, veja [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
