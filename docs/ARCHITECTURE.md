# AgentForge — Arquitetura Técnica

Referência técnica completa do framework. Cobre todos os módulos, fluxos de execução, contratos de API interna e decisões de design.

---

## Visão Geral

```
Spec (agent.yaml)
    │
    ▼
AgentRuntime.from_agent_dir()
    │
    ├── _read_system_prompt()
    ├── _build_tools_schema()
    │
    ▼
run(input_text)
    │
    ├── [required_tool] → _execute_tool() → injeta resultado
    │
    ├── [respond_or_tool] → _run_tool_calling_cycle()
    │       └── loop: infer → tool_call? → execute → repeat
    │              loop_guard: para em (tool, args) repetido
    │              final_inference: gera output após ciclos
    │
    ├── [direto] → provider.generate()
    │
    ├── _reflect() × N rounds
    │
    ├── _apply_guardrails()
    │       └── _check_guardrail_violations() × até 2 retries
    │
    └── _log_run() → runs.jsonl
```

---

## Módulos

### `core/agent_models.py`

Todos os tipos do `AgentSpec` via Pydantic v2. `extra="forbid"` em todos — erro explícito em campos desconhecidos no YAML.

**Hierarquia:**

```
AgentSpec
├── AgentIdentity       id, name, purpose
├── AgentPersona        tone, style, personality
├── ChannelSpec         type, interface
├── ToolSpec[]          name, required, description, when_to_use,
│                       when_not_to_use, input_schema, output_schema
├── MemorySpec          type, enabled, max_turns, policy
├── OutputSpec          mode, format
├── GuardrailSpec       must[], must_not[], optional[]
├── EvaluationSpec      user_score_enabled, criteria[], judge_model
├── DeploymentSpec      provider
├── ModelPolicySpec     default_model, fallback_model
└── WorkflowSpec        mode, multi_turn, max_tool_cycles, reflection_rounds
```

**WorkflowSpec.mode:**
- `respond_or_tool` — tool calling model-driven (padrão para agentes com ferramentas)
- qualquer outro valor — resposta direta sem tool calling

---

### `runtime/engine.py`

**`RuntimeConfig`** — view plana da spec para o engine (evita acesso aninhado em hot paths):

```python
RuntimeConfig(
    agent_id, provider, model_default, model_fallback,
    workflow_mode, channel_type,
    memory_enabled, memory_type, memory_max_turns, memory_policy,
    output_mode, output_format, conversation_multi_turn,
    max_tool_cycles, reflection_rounds,
)
```

**`AgentRuntime.run(input_text, *, metadata=None) → dict`**

Retorna:

```python
{
    "agent_id": str,
    "provider": str,
    "input": str,
    "output": str,
    "metadata": {
        "provider": str,
        "workflow_mode": str,
        "model_default": str,
        "timestamp": ISO8601,
        "latency_ms": int,
        "tool_executed": str | None,        # required_tool se usado
        "tool_data": dict | None,
        "tool_calls_log": list[dict] | None, # ciclos respond_or_tool
        "conversation_turn": int,
        "guardrail_violations": list[str] | None,
    },
    "provider_response": {
        "provider": str,
        "model": str,
        "raw_response": dict | None,
    },
}
```

**`_run_tool_calling_cycle(input_text, system_prompt, history)`**

Loop de até `max_tool_cycles` iterações:
- Ciclo 0: `ProviderRequest(history=messages[:-1], tools_schema=schema)`
- Ciclos 1+: `ProviderRequest(history=messages, tools_schema=schema)`
- `tools_schema=None` quando lista vazia (falsy → rota para `_generate_simple`)
- Loop guard: `seen_calls: set[str]` com chave `f"{tool_name}:{json(args)}"`
- Final: `response.tool_calls is None` → retorna; ou ciclos esgotados → inferência final sem tools

**`_reflect(original_input, output_text, system_prompt, rounds)`**

Auto-crítica estacionária (sem histórico, sem tools). Cada round aplica prompt estruturado:
1. Completa e precisa?
2. Respeita restrições do papel?
3. Pode ser mais objetiva?

**`_check_guardrail_violations(output_text) → list[str]`**

Usa o próprio modelo (`_generate_simple`, sem histórico) para identificar violações:
- Input: lista de `must_not` + texto do output
- Output esperado: "NENHUMA" ou lista de regras violadas, uma por linha
- Retorna `[]` se "NENHUMA" ou resposta vazia

**`_apply_guardrails(input_text, output_text, system_prompt, history, max_retries=2)`**

1. Chama `_check_guardrail_violations`
2. Se sem violações: retorna imediatamente
3. Para cada retry: gera prompt de correção → re-inferência → re-verifica
4. Retorna `(output_text_final, violations_restantes)`

**`_log_run(result, latency_ms)`**

Append-only em `agents/<id>/runs/runs.jsonl`. Formato: uma linha JSON por run com campos resumidos.

---

### `providers/ollama.py`

**Roteamento por tipo de request:**

```python
def generate(request: ProviderRequest) -> ProviderResponse:
    if request.history or request.tools_schema:
        return self._generate_chat(request)     # POST /api/chat
    return self._generate_simple(request)        # POST /api/generate
```

- `_generate_simple`: payload `{"model", "prompt", "stream": false}`
- `_generate_chat`: payload `{"model", "messages", "stream": false, "tools"?}`

**Parsing de tool_calls** (`_generate_chat`):

```python
# Resposta Ollama/OpenAI format
message.tool_calls → [{"function": {"name": ..., "arguments": ...}}]
# Normalizado para:
[{"name": str, "arguments": dict}]
```

**`ProviderRequest`:**
```python
class ProviderRequest(BaseModel):
    agent_id: str
    input_text: str
    system_prompt: str | None
    model: str
    history: list[dict[str, str]] = []
    tools_schema: list[dict[str, Any]] | None = None
    max_tokens: int = 16384
```

**`ProviderResponse`:**
```python
class ProviderResponse(BaseModel):
    output_text: str
    raw_response: dict | None = None
    tool_calls: list[dict[str, Any]] | None = None
```

---

### `providers/mock.py`

Retorna respostas determinísticas sem chamar Ollama. Usado em todos os testes. Configurado via `deployment.provider: mock` no `agent.yaml`.

---

### `runtime/memory.py`

**`load_history(root_dir, memory_type, enabled, max_turns, policy) → list`**

Carrega `history.json` se existir e se `enabled=True`.

**`save_history(root_dir, history)`**

Persiste em `history.json`.

**`apply_window(history, max_turns, policy) → list`**

- `policy="truncate"`: mantém as últimas `max_turns` mensagens
- `policy="summarize"`: condensa mensagens antigas em bullet-points determinísticos

---

### `tools/registry.py`

**`execute_tool(name, **kwargs) → dict | None`**

Dispatcher por nome. Ferramentas registradas:

| Nome | Módulo | Descrição |
|---|---|---|
| `collect_system_health` | `tools/system_health.py` | CPU, RAM, disco, GPU, processos |
| `read_log_tail` | `tools/read_log_tail.py` | Últimas N linhas de um arquivo de log |
| `scan_directory` | `tools/vault_scan.py` | Lista arquivos de um diretório |
| `vault_extract` | `tools/vault_extract.py` | Extrai conteúdo de arquivo do vault |

---

### `eval/judge.py`

**`score(input_text, output_text, criteria, judge_model) → dict`**

Pontua o output contra critérios de 0–100 cada:

```python
{
    "scores": {"critério 1": 85, "critério 2": 70},
    "total": 155,
    "pct": 77,
    "justificativas": {"critério 1": "...", "critério 2": "..."},
}
```

Suporte a:
- `judge_model` começando com `"gemini-"` → chama API Gemini
- qualquer outro → chama Ollama local

---

### `channels/http.py`

FastAPI app criado por `create_app(runtime) → FastAPI`.

**Endpoints:**
- `GET /health` → `HealthResponse(status, agent_id, agent_name, model, provider)`
- `POST /run` → `RunResponse(agent_id, output, latency_ms, provider, model, tool_calls_log)`

---

### `channels/mcp_server.py`

Servidor FastMCP com 4 ferramentas:

| Ferramenta MCP | O que faz |
|---|---|
| `collect_system_health` | Executa a tool diretamente e retorna JSON |
| `read_log_tail` | Lê as últimas N linhas do log informado |
| `scan_directory` | Lista arquivos de um diretório (max 100) |
| `run_agent` | Executa um agente completo por `agent_dir` + `input` |

Transporte: `stdio` (Claude Code) ou HTTP/SSE.

---

### `channels/telegram.py`

Bot assíncrono via `python-telegram-bot>=20.7`.

**`make_message_handler(runtime) → async handler`**

Handler assíncrono:
1. Filtra mensagens sem texto ou com texto vazio
2. Envia `send_chat_action("typing")`
3. Chama `runtime.run(text)` (síncrono, thread do event loop)
4. Se `guardrail_violations` → appenda aviso no reply
5. Em erro → reply com mensagem genérica (sem stack trace)

**`create_application(runtime, token) → Application`**

Registra o handler em `filters.TEXT & ~filters.COMMAND`.

**`run_polling(runtime, token)`**

Inicia polling blocking.

---

## Contratos de Tool Calling

O protocolo seguido é o formato OpenAI/Ollama nativo:

**Schema de ferramenta (enviado para o modelo):**
```json
{
  "type": "function",
  "function": {
    "name": "collect_system_health",
    "description": "Coleta métricas... Use quando: ... Não use quando: ...",
    "parameters": {"type": "object", "properties": {}}
  }
}
```

**Resposta do modelo com tool call:**
```json
{
  "message": {
    "content": "",
    "tool_calls": [
      {"function": {"name": "collect_system_health", "arguments": {}}}
    ]
  }
}
```

**Resultado injetado de volta:**
```
<tool_results>
{"tool": "collect_system_health", "result": {...}}
</tool_results>

User: <input original>
```

---

## Loop Guard

Implementado em `_run_tool_calling_cycle`. Chave de detecção:

```python
call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
if call_key in seen_calls:
    loop_detected = True
    break
seen_calls.add(call_key)
```

Quando loop detectado: executa todos os tool calls do ciclo atual, depois faz inferência final com histórico acumulado e `tools_schema=None` (sem tools disponíveis para evitar novo loop).

---

## Pipeline Completo de run()

```
run(input_text)
  │
  ├── [required_tool resolvido da spec]
  │     execute_tool() → injeta em final_input
  │
  ├── mode == "respond_or_tool"
  │     _run_tool_calling_cycle()
  │       └── for cycle in range(max_tool_cycles):
  │             provider.generate(tools_schema=schema)
  │             if no tool_calls: return output
  │             execute tools, inject results
  │             if loop_guard: final_inference without tools
  │           final_inference without tools (exaustão)
  │
  ├── mode != "respond_or_tool"
  │     provider.generate() direto
  │
  ├── reflection_rounds > 0
  │     _reflect() × N
  │
  ├── must_not não vazio
  │     _apply_guardrails()
  │       _check_guardrail_violations()
  │       if violations: correction + re-inference × max_retries
  │
  ├── multi_turn: update _history, apply_window, save_history
  │
  ├── _log_run() → runs.jsonl
  │
  └── return result dict
```

---

## Testes

**291 testes em 7 arquivos:**

| Arquivo | Cobertura |
|---|---|
| `test_runtime_engine.py` | RuntimeConfig, AgentRuntime, tool calling, loop guard, reflexão, guardrails, eval |
| `test_http_channel.py` | FastAPI `/health` e `/run`, erros, tool_calls_log |
| `test_mcp_server.py` | Registro de ferramentas, collect_system_health, read_log_tail, run_agent |
| `test_telegram_channel.py` | Handler assíncrono, typing action, erros, guardrail warning, create_application |
| `test_agent_models.py` | AgentSpec, todos os sub-specs, validação |
| `test_validation.py` | YAML load, validate_agent_spec |
| `test_wizard.py` | Wizard flow |

**Estratégia de mock:**

- Testes de runtime: `monkeypatch(requests, "post", Mock(...))` — intercepta chamadas HTTP ao Ollama
- Formato `_mock_simple_resp(text)` → `{"response": text}` (rota `_generate_simple`)
- Formato `_mock_chat_text_resp(text)` → `{"message": {"content": text}}` (rota `_generate_chat`)
- Formato `_mock_chat_tool_call_resp(name)` → `{"message": {"tool_calls": [...]}}` (tool call)
- Testes de canal Telegram: `MagicMock()` + `AsyncMock()` para `Update` e `Context`
