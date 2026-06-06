# AgentForge — Technical Architecture

Complete technical reference for the framework. Covers all modules, execution flows, internal API contracts, and design decisions.

---

## Overview

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
    ├── [required_tool] → _execute_tool() → injects result
    │
    ├── [respond_or_tool] → _run_tool_calling_cycle()
    │       └── loop: infer → tool_call? → execute → repeat
    │              loop_guard: stops on repeated (tool, args)
    │              final_inference: generates output after cycles
    │
    ├── [direct] → provider.generate()
    │
    ├── _reflect() × N rounds
    │
    ├── _apply_guardrails()
    │       └── _check_guardrail_violations() × up to 2 retries
    │
    └── _log_run() → runs.jsonl
```

---

## Modules

### `core/agent_models.py`

All `AgentSpec` types via Pydantic v2. `extra="forbid"` on all — explicit error on unknown fields in YAML.

**Hierarchy:**

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
- `respond_or_tool` — model-driven tool calling (default for agents with tools)
- any other value — direct response without tool calling

---

### `runtime/engine.py`

**`RuntimeConfig`** — flat view of the spec for the engine (avoids nested access in hot paths):

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

Returns:

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
        "tool_executed": str | None,        # required_tool if used
        "tool_data": dict | None,
        "tool_calls_log": list[dict] | None, # respond_or_tool cycles
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

Loop of up to `max_tool_cycles` iterations:
- Cycle 0: `ProviderRequest(history=messages[:-1], tools_schema=schema)`
- Cycles 1+: `ProviderRequest(history=messages, tools_schema=schema)`
- `tools_schema=None` when list is empty (falsy → routes to `_generate_simple`)
- Loop guard: `seen_calls: set[str]` with key `f"{tool_name}:{json(args)}"`
- Final: `response.tool_calls is None` → returns; or cycles exhausted → final inference without tools

**`_reflect(original_input, output_text, system_prompt, rounds)`**

Stationary self-critique (no history, no tools). Each round applies a structured prompt:
1. Complete and accurate?
2. Respects role constraints?
3. Can it be more concise?

**`_check_guardrail_violations(output_text) → list[str]`**

Uses the model itself (`_generate_simple`, no history) to identify violations:
- Input: list of `must_not` + output text
- Expected output: "NONE" or list of violated rules, one per line
- Returns `[]` if "NONE" or empty response

**`_apply_guardrails(input_text, output_text, system_prompt, history, max_retries=2)`**

1. Calls `_check_guardrail_violations`
2. If no violations: returns immediately
3. For each retry: generates correction prompt → re-inference → re-checks
4. Returns `(output_text_final, remaining_violations)`

**`_log_run(result, latency_ms)`**

Append-only to `agents/<id>/runs/runs.jsonl`. Format: one JSON line per run with summarized fields.

---

### `providers/ollama.py`

**Routing by request type:**

```python
def generate(request: ProviderRequest) -> ProviderResponse:
    if request.history or request.tools_schema:
        return self._generate_chat(request)     # POST /api/chat
    return self._generate_simple(request)        # POST /api/generate
```

- `_generate_simple`: payload `{"model", "prompt", "stream": false}`
- `_generate_chat`: payload `{"model", "messages", "stream": false, "tools"?}`

**Parsing tool_calls** (`_generate_chat`):

```python
# Ollama/OpenAI format response
message.tool_calls → [{"function": {"name": ..., "arguments": ...}}]
# Normalized to:
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

Returns deterministic responses without calling Ollama. Used in all tests. Configured via `deployment.provider: mock` in `agent.yaml`.

---

### `runtime/memory.py`

**`load_history(root_dir, memory_type, enabled, max_turns, policy) → list`**

Loads `history.json` if it exists and if `enabled=True`.

**`save_history(root_dir, history)`**

Persists to `history.json`.

**`apply_window(history, max_turns, policy) → list`**

- `policy="truncate"`: keeps the last `max_turns` messages
- `policy="summarize"`: condenses old messages into deterministic bullet points

---

### `tools/registry.py`

**`execute_tool(name, **kwargs) → dict | None`**

Dispatcher by name. Registered tools:

| Name | Module | Description |
|---|---|---|
| `collect_system_health` | `tools/system_health.py` | CPU, RAM, disk, GPU, processes |
| `read_log_tail` | `tools/read_log_tail.py` | Last N lines of a log file |
| `scan_directory` | `tools/vault_scan.py` | Lists files in a directory |
| `vault_extract` | `tools/vault_extract.py` | Extracts content from a vault file |

---

### `eval/judge.py`

**`score(input_text, output_text, criteria, judge_model) → dict`**

Scores output against criteria from 0–100 each:

```python
{
    "scores": {"criterion 1": 85, "criterion 2": 70},
    "total": 155,
    "pct": 77,
    "justifications": {"criterion 1": "...", "criterion 2": "..."},
}
```

Supports:
- `judge_model` starting with `"gemini-"` → calls Gemini API
- any other → calls local Ollama

---

### `channels/http.py`

FastAPI app created by `create_app(runtime) → FastAPI`.

**Endpoints:**
- `GET /health` → `HealthResponse(status, agent_id, agent_name, model, provider)`
- `POST /run` → `RunResponse(agent_id, output, latency_ms, provider, model, tool_calls_log)`

---

### `channels/mcp_server.py`

FastMCP server with 4 tools:

| MCP Tool | What it does |
|---|---|
| `collect_system_health` | Executes the tool directly and returns JSON |
| `read_log_tail` | Reads the last N lines of the given log |
| `scan_directory` | Lists files in a directory (max 100) |
| `run_agent` | Runs a full agent by `agent_dir` + `input` |

Transport: `stdio` (Claude Code) or HTTP/SSE.

---

### `channels/telegram.py`

Async bot via `python-telegram-bot>=20.7`.

**`make_message_handler(runtime) → async handler`**

Async handler:
1. Filters messages without text or with empty text
2. Sends `send_chat_action("typing")`
3. Calls `runtime.run(text)` (synchronous, event loop thread)
4. If `guardrail_violations` → appends warning to reply
5. On error → reply with generic message (no stack trace)

**`create_application(runtime, token) → Application`**

Registers the handler on `filters.TEXT & ~filters.COMMAND`.

**`run_polling(runtime, token)`**

Starts blocking polling.

---

## Tool Calling Contracts

The protocol followed is the native OpenAI/Ollama format:

**Tool schema (sent to the model):**
```json
{
  "type": "function",
  "function": {
    "name": "collect_system_health",
    "description": "Collects metrics... Use when: ... Do not use when: ...",
    "parameters": {"type": "object", "properties": {}}
  }
}
```

**Model response with tool call:**
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

**Result injected back:**
```
<tool_results>
{"tool": "collect_system_health", "result": {...}}
</tool_results>

User: <original input>
```

---

## Loop Guard

Implemented in `_run_tool_calling_cycle`. Detection key:

```python
call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
if call_key in seen_calls:
    loop_detected = True
    break
seen_calls.add(call_key)
```

When a loop is detected: executes all tool calls from the current cycle, then performs final inference with accumulated history and `tools_schema=None` (no tools available to prevent a new loop).

---

## Complete run() Pipeline

```
run(input_text)
  │
  ├── [required_tool resolved from spec]
  │     execute_tool() → injects into final_input
  │
  ├── mode == "respond_or_tool"
  │     _run_tool_calling_cycle()
  │       └── for cycle in range(max_tool_cycles):
  │             provider.generate(tools_schema=schema)
  │             if no tool_calls: return output
  │             execute tools, inject results
  │             if loop_guard: final_inference without tools
  │           final_inference without tools (exhaustion)
  │
  ├── mode != "respond_or_tool"
  │     provider.generate() direct
  │
  ├── reflection_rounds > 0
  │     _reflect() × N
  │
  ├── must_not not empty
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

## Tests

**291 tests across 7 files:**

| File | Coverage |
|---|---|
| `test_runtime_engine.py` | RuntimeConfig, AgentRuntime, tool calling, loop guard, reflection, guardrails, eval |
| `test_http_channel.py` | FastAPI `/health` and `/run`, errors, tool_calls_log |
| `test_mcp_server.py` | Tool registration, collect_system_health, read_log_tail, run_agent |
| `test_telegram_channel.py` | Async handler, typing action, errors, guardrail warning, create_application |
| `test_agent_models.py` | AgentSpec, all sub-specs, validation |
| `test_validation.py` | YAML load, validate_agent_spec |
| `test_wizard.py` | Wizard flow |

**Mock strategy:**

- Runtime tests: `monkeypatch(requests, "post", Mock(...))` — intercepts HTTP calls to Ollama
- Format `_mock_simple_resp(text)` → `{"response": text}` (`_generate_simple` route)
- Format `_mock_chat_text_resp(text)` → `{"message": {"content": text}}` (`_generate_chat` route)
- Format `_mock_chat_tool_call_resp(name)` → `{"message": {"tool_calls": [...]}}` (tool call)
- Telegram channel tests: `MagicMock()` + `AsyncMock()` for `Update` and `Context`
