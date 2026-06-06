**[🇧🇷 Versão em Português](README.pt-BR.md)**

# AgentForge

Python framework **spec-first** and **local-first** for creating, experimenting with, and running LLM agents on-premise.

AgentForge encapsulates the central thesis empirically validated through 4 months of benchmarks (ABS → LOP → FORGE → REAL):

> **20% is the model, 80% is the runtime.**

The quality of a local agent depends less on the chosen model and more on how the runtime manages context, tool use decisions, guardrails, and evaluation. The framework implements these mechanisms in an explicit, testable, and spec-driven way.

---

## Table of Contents

- [Key Features](#key-features)
- [Requirements & Installation](#requirements--installation)
- [Basic Flow](#basic-flow)
- [Execution Channels](#execution-channels)
- [Tool Calling](#tool-calling)
- [Tool Registry — Agents That Create Tools](#tool-registry--agents-that-create-tools)
- [Active Guardrails](#active-guardrails)
- [Autonomous Reflection](#autonomous-reflection)
- [Evaluation & Scoring](#evaluation--scoring)
- [Project Structure](#project-structure)
- [CLI Reference](#cli-reference)
- [Development & Testing](#development--testing)

---

## Key Features

| Feature | What it means in practice |
|---|---|
| **Spec-First** | An agent is born from an `agent.yaml`. No behavior exists outside the spec. |
| **Local-First** | Optimized for Ollama. No external API dependencies in the critical path. |
| **Tool Calling Model-Driven** | The model decides when to call tools via the native OpenAI/Ollama protocol. |
| **Loop Guard** | Detects repeated tool calling cycles and stops before exhausting the budget. |
| **Autonomous Reflection** | N rounds of self-critique after the initial output — improves quality without human intervention. |
| **Active Guardrails** | Checks `must_not` on the output using the model itself as judge. Automatically retries if violated. |
| **Eval with LLM Judge** | Multidimensional scoring using local Ollama or Gemini as evaluator. |
| **4 Channels** | CLI, HTTP (n8n), MCP (Claude Code/Desktop), Telegram — same spec, any interface. |
| **Multi-Agent** | Orchestrator delegates subtasks to workers declared in the YAML via `run_agent`. |
| **Tool Registry** | Agents create, test, and register new Python tools at runtime. Tools become permanently available to all agents. |
| **296 tests** | Broad coverage ensuring runtime stability and API contracts. |

---

## Requirements & Installation

**Requirements:**
- Python 3.11+
- Ollama installed and running (`docker compose` or local)
- Recommended model: `qwen3.5:9b` (simple tasks) or `qwen3.5:27b` (complex tasks)

### Recommended Models

AgentForge works with any Ollama model, but was **empirically optimized for the qwen3.5 family** based on 4 months of benchmarks (ABS → LOP → FORGE → REAL) covering 19 local models.

| Model | VRAM | Speed* | Recommended use |
|---|---|---|---|
| `qwen3.5:9b` | ~7 GB | ~45 tok/s | Monitoring, orchestration, simple queries |
| `qwen3.5:27b` | ~17 GB | ~25 tok/s | Coding with tests, multi-step analysis, documentation generation |

*Measured on test hardware (Xeon E5-2696v3 + dual RTX 3060 12GB).

Results on evaluation scenarios with qwen3.5:27b: **FORGE F3 94.4%**, **REAL P4 91.7%**.

> Methodological details and selection criteria: [`docs/MODEL-STRATEGY.md`](docs/MODEL-STRATEGY.md)

```bash
git clone <repo-url>
cd agents-framework
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Basic Flow

Every agent follows three steps:

### 1. Create the specification

```bash
agentforge wizard
```

Generates `agents/<id>/agent.yaml` with persona, tools, memory, and guardrails.

### 2. Generate artifacts

```bash
agentforge generate --path agents/<id>/agent.yaml
```

Produces in `agents/<id>/`:
- `system_prompt.md` — structured system prompt
- `runtime.yaml` — execution parameters
- `tools.yaml` — tool schema
- `eval.yaml` — evaluation configuration
- `README.md` — agent technical documentation

### 3. Run

```bash
agentforge run --agent-dir agents/lab-ops --input "How is the server?"
```

Output in JSON (`--mode raw`) or human-readable text (`--mode pretty`).

---

## Execution Channels

The same agent runs on four channels without changing the spec:

### CLI (default)

```bash
agentforge run --agent-dir agents/lab-ops --input "text" --mode pretty
```

### HTTP — integration with n8n and automations

```bash
agentforge serve --agent-dir agents/lab-ops --port 8080
```

```http
POST http://localhost:8080/run
Content-Type: application/json
{"input": "server status"}

GET  http://localhost:8080/health
```

### MCP — tools for Claude Code / Claude Desktop

```bash
agentforge mcp --transport stdio
```

Configure in `.mcp.json` at the project root:

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

Exposed tools: `collect_system_health`, `read_log_tail`, `scan_directory`, `run_agent`.

### Telegram

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC..."
agentforge telegram --agent-dir agents/lab-ops
```

The bot receives text messages, runs the agent, and replies. Shows "typing..." during processing and signals in the reply if guardrails were triggered.

---

## Tool Calling

The `respond_or_tool` mode activates the model-driven tool calling pipeline:

```yaml
# agent.yaml
workflow:
  mode: respond_or_tool
  max_tool_cycles: 5
```

**Flow per cycle:**
1. Inference with tool schema (native OpenAI/Ollama protocol)
2. Model decides: direct response **or** tool call
3. If tool call → execute → inject result → next cycle
4. **Loop guard**: stops if the same `(tool, args)` repeats in the same cycle
5. Upon exhausting `max_tool_cycles` → final inference with all accumulated results

**Useful fields in ToolSpec:**

```yaml
tools:
  - name: collect_system_health
    description: "Collects CPU, RAM, disk, and GPU metrics"
    when_to_use: "Whenever the user asks about server status"
    when_not_to_use: "Do not use for questions about specific logs"
```

`when_to_use` and `when_not_to_use` are injected into the tool description — they act as decision hints that reduce incorrect calls in local models.

---

## Tool Registry — Agents That Create Tools

AgentForge implements the **Voyager** pattern: agents create new Python tools during execution, test them with real pytest, and register them permanently. Every registered tool becomes available to any agent in the next session — no restart needed.

**Full flow:**

```
tool-builder receives description
    → write_file: implementation.py
    → read_file: re-reads before writing tests (consistency)
    → write_file: test_implementation.py
    → run_bash: pytest (real tests, no mocks)
    → register_tool_file: copies to tool_registry/ + updates registry.yaml
    → Tool available immediately and in every future session
```

**Using the tool-builder:**

```bash
agentforge run --agent-dir agents/tool-builder --input "
Create a Python tool called rate_limiter that controls requests per sliding window.
After pytest passes, register it in the framework.
"
```

**Using a registered tool in another agent:**

```yaml
# agent.yaml
tools:
  - name: search_memory
    description: Searches agent-mesh shared_memory by LIKE query on key and value.
    when_to_use: "Use to retrieve context from previous sessions."
    input_schema: '{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}'
```

**Tools available in `tool_registry/`:**

| Tool | Description |
|---|---|
| `search_memory` | Searches `~/.agent-mesh/state.db` by LIKE on key and value. Returns top-3. |

> Full documentation: [`docs/TOOL-REGISTRY.md`](docs/TOOL-REGISTRY.md)

---

## Active Guardrails

Guardrails are checked **after** the output is generated, before returning to the user.

```yaml
# agent.yaml
guardrails:
  must:
    - always use real data from tools
    - provide evidence-based recommendations
  must_not:
    - fabricate metrics
    - access files outside the logs directory
    - modify any system file
```

**Runtime behavior:**
1. Output generated (tool calling or direct response)
2. Autonomous reflection applied (if configured)
3. The model analyzes its own output against `must_not` rules
4. If violation detected: correction prompt + re-inference (up to 2 retries)
5. Persistent violations recorded in `result["metadata"]["guardrail_violations"]`

---

## Multi-Agent Orchestration

An orchestrator is a regular agent that declares workers in `workflow.agents`. The engine automatically injects `run_agent` into the tool schema — the model decides when and to whom to delegate.

```yaml
# agents/orchestrator/agent.yaml
workflow:
  mode: respond_or_tool
  max_tool_cycles: 8
  agents:
    - name: lab-ops
      agent_dir: agents/lab-ops
      description: Server health monitoring and log inspection
    - name: another-agent
      agent_dir: agents/another-agent
      description: Document analysis
```

**Delegation flow:**
1. Orchestrator receives task from user
2. Model analyzes and decides to delegate → calls `run_agent(agent_dir=..., input=...)`
3. Engine loads the worker, runs `runtime.run(input)`, returns the output
4. Worker output is injected into the orchestrator's history
5. Orchestrator synthesizes all results into a final response

Workers only appear in the schema if declared — the model cannot invent agents outside the spec.

```bash
agentforge run --agent-dir agents/orchestrator --input "Full server report"
```

## Autonomous Reflection

The agent can review its own output before returning:

```yaml
# agent.yaml
workflow:
  mode: respond_or_tool
  reflection_rounds: 2
```

Each round applies a structured self-critique prompt:
- Is the response complete and accurate?
- Does it respect the role constraints?
- Can it be more objective?

Reflection is stateless (no history) and runs N times sequentially.

---

## Evaluation & Scoring

### Dataset evaluation

```bash
agentforge eval \
  --agent-dir agents/lab-ops \
  --dataset agents/lab-ops/eval_dataset.yaml
```

Dataset format:

```yaml
cases:
  - input: "How is the server health?"
    notes: "should collect real data before responding"
  - input: "Are there errors in the latest system logs?"
    notes: "should use read_log_tail"
```

Results saved to `agents/<id>/eval_runs/<timestamp>.jsonl`.

### LLM Judge

Enable automatic scoring in `agent.yaml`:

```yaml
eval:
  judge_model: "gemma4:e4b"
  criteria:
    - response based on real data
    - objective and actionable recommendation
    - no fabricated metrics
```

The judge scores each criterion from 0–100 and calculates an average score. Supports local Ollama models or `gemini-*` via Gemini API.

---

## Project Structure

```
agents-framework/
├── agents/                    # Agents (each self-contained)
│   ├── lab-ops/               # Infra monitoring (reference agent)
│   ├── tool-builder/          # Creates and registers Python tools
│   ├── forge-f3/              # FX + crypto analysis (FORGE F3 benchmark)
│   ├── real-p3/               # Python tool with real tests (REAL P3 benchmark)
│   ├── real-p4/               # Skill generator (REAL P4 benchmark)
│   └── orchestrator/          # Multi-agent orchestrator
│
├── tool_registry/             # Tools generated by agents
│   ├── registry.yaml          # Persistent manifest (managed automatically)
│   └── search_memory.py       # Searches agent-mesh shared_memory
│
├── src/agentforge/
│   ├── channels/              # Execution channels
│   │   ├── http.py            # FastAPI REST (n8n, automations)
│   │   ├── mcp_server.py      # FastMCP (Claude Code/Desktop)
│   │   └── telegram.py        # Telegram bot (async polling)
│   ├── providers/
│   │   ├── ollama.py          # Ollama integration (chat + generate + think:false)
│   │   └── mock.py            # Deterministic provider for tests
│   ├── runtime/
│   │   ├── engine.py          # AgentRuntime: full pipeline
│   │   └── memory.py          # History, window, persistence
│   ├── tools/
│   │   ├── registry.py        # _ToolRegistry: builtins + dynamic
│   │   ├── dynamic_loader.py  # Loads tool_registry/ on init
│   │   ├── register_tool_file.py  # Validates, copies, and registers Python files
│   │   ├── write_file.py      # File read/write (AGENT_WORKDIR)
│   │   ├── run_bash.py        # Bash with destructive command blocklist
│   │   ├── http_get.py        # HTTP GET
│   │   └── send_claudio.py    # Telegram notification (Claudio bot)
│   └── generators/
│       └── agent_files.py     # Artifact generation from spec
│
├── scripts/
│   └── run_benchmark_eval.py  # FORGE + REAL scenario runner
│
├── tests/                     # 278 tests (MockProvider, no Ollama required)
├── docs/
│   ├── ARCHITECTURE.md        # Full technical reference
│   ├── MODEL-STRATEGY.md      # qwen3.5 model selection (empirical)
│   ├── FINETUNING-STRATEGY.md # LoRA fine-tuning strategy
│   └── TOOL-REGISTRY.md       # Tool Registry: agents that create tools
├── .mcp.json                  # MCP config for Claude Code
└── pyproject.toml
```

---

## CLI Reference

| Command | Description |
|---|---|
| `agentforge wizard` | Creates spec interactively |
| `agentforge generate --path <yaml>` | Generates artifacts from spec |
| `agentforge validate [--root .]` | Validates framework specs |
| `agentforge validate-agent --path <yaml>` | Validates an agent.yaml |
| `agentforge run --agent-dir <dir> --input <text>` | Runs the agent |
| `agentforge eval --agent-dir <dir> --dataset <yaml>` | Evaluates with dataset |
| `agentforge serve --agent-dir <dir> [--port 8080]` | Starts HTTP API |
| `agentforge mcp [--transport stdio\|http]` | Starts MCP server |
| `agentforge telegram --agent-dir <dir> [--token <tok>]` | Starts Telegram bot |

---

## Development & Testing

```bash
# All tests
pytest -q

# Specific file
pytest tests/test_runtime_engine.py -v

# HTTP channel
pytest tests/test_http_channel.py -v

# Telegram channel
pytest tests/test_telegram_channel.py -v
```

The project uses `MockProvider` (`deployment.provider: mock`) for deterministic tests — no Ollama required in CI.

For detailed technical documentation, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
