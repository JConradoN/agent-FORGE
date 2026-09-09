---
type: Reference
title: AgentForge — Quick Start
description: Entry point for the AgentForge wiki — install, the spec → generate → run loop, the four execution channels, and a routing map to every page in the hierarchy.
tags: [quickstart, agentforge, cli, channels, spec, routing]
openwiki_generated: true
verified:
  - by: openwiki/0.5.0
    at: 2026-09-09T12:43:13.007Z
sources:
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-192f747a98eaaf882d277a9f
    resource: repo://src/agentforge/channels/http.py
  - id: openwiki-source-bb51ef125fd644348f8339d5
    resource: repo://src/agentforge/channels/mcp_server.py
  - id: openwiki-source-e7edf7f9ca6da0a06f77a279
    resource: repo://src/agentforge/channels/telegram.py
  - id: openwiki-source-e300a418178b3d1148ca76b2
    resource: repo://src/agentforge/cli/main.py
  - id: openwiki-source-6d3e09b4383068b34b810dbc
    resource: repo://src/agentforge/generators/agent_files.py
  - id: openwiki-source-02a45f09cc1e6782644c0f1a
    resource: repo://src/agentforge/runtime/engine.py
generated: { by: "openwiki/0.5.0", at: "2026-09-09T12:43:13.007Z" }
---

# AgentForge — Quick Start

**AgentForge** is a Python **spec-first**, **local-first** framework for creating, experimenting with, and running LLM agents on-premise. It is the production destination of a 4-stage model certification funnel (ABS → LOP → FORGE → REAL) that passed 19 models through elimination gates. Its central thesis, validated across 4 months of benchmarking, is:

> **20% is the model, 80% is the runtime.**

The quality of a local agent depends more on how the runtime manages context, tool-use decisions, guardrails, and evaluation than on the model itself. The framework implements those mechanisms explicitly, testably, and spec-driven.

## What This Wiki Covers

| Capability | Details |
|------------|---------|
| **Spec-driven agents** | Every agent is defined by an `agent.yaml` — no behavior exists outside the spec |
| **Tool calling** | Model-driven tool use via the native OpenAI/Ollama protocol with loop guards |
| **Multi-agent orchestration** | Agents delegate to workers via the auto-injected `run_agent` tool |
| **Active guardrails** | `must_not` violations auto-corrected (up to 2 retries); `must` rules enforced with correction retries |
| **Autonomous reflection** | N rounds of self-critique after the initial output |
| **4 execution channels** | CLI, HTTP (n8n), MCP (Claude Code/Desktop), Telegram |
| **Tool registry** | Agents create and register new Python tools at runtime (Voyager pattern) |
| **Evaluation** | Dataset-based eval + LLM judge scoring |
| **Finetuning** | LoRA fine-tuning pipeline with synthetic data generation |

## Getting Started

### Prerequisites

- Python 3.11+ (`requires-python = ">=3.11"` in `pyproject.toml`)
- Ollama installed and running (`docker compose` or local)
- Recommended models: `qwen3.5:9b` (~7 GB VRAM, simple tasks) or `qwen3.5:27b` (~17 GB VRAM, complex tasks)

### Installation

The package is named `agents-framework` and exposes the `agentforge` console script (a Typer app at `agentforge.cli.main:app`):

```bash
git clone <repo-url>
cd agents-framework
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### The install → spec → generate → run loop

Every agent follows the same three-step loop; the spec is the single source of truth:

**Step 1 — Create the spec (`agentforge wizard`)**

```bash
agentforge wizard
```

Interactive wizard (identity, persona, provider/model, workflow, memory, guardrails, tools) that writes `agents/<id>/agent.yaml`.

**Step 2 — Generate artifacts (`agentforge generate`)**

```bash
agentforge generate --path agents/<id>/agent.yaml
```

`generate_agent_files()` validates the spec and writes five artifacts next to it: `system_prompt.md`, `runtime.yaml`, `eval.yaml`, `tools.yaml`, `README.md`.

**Step 3 — Run the agent (`agentforge run`)**

```bash
agentforge run --agent-dir agents/lab-ops --input "How is the server?"
```

`AgentRuntime.from_agent_dir()` loads the spec + `runtime.yaml` (+ optional `tools.yaml`), then `runtime.run(input)` executes the full pipeline. Output is JSON (`--mode raw`, the default) or human-readable (`--mode pretty`). Every run is appended to `agents/<id>/runs/runs.jsonl`.

## Execution Channels

The same agent spec runs on four channels without modification. Each channel wraps the same `AgentRuntime.run()` entrypoint:

| Channel | Command | Entry point | Use case |
|---------|---------|-------------|----------|
| **CLI** | `agentforge run --agent-dir agents/lab-ops --input "text"` | `agentforge.cli.main:run` | Direct interaction |
| **HTTP** | `agentforge serve --agent-dir agents/lab-ops --port 8080` | `agentforge.channels.http:create_app` (FastAPI, `POST /run` + `GET /health`) | n8n / automation integration |
| **MCP** | `agentforge mcp --transport stdio` | `agentforge.channels.mcp_server` (FastMCP: `collect_system_health`, `read_log_tail`, `scan_directory`, `run_agent`) | Claude Code / Claude Desktop |
| **Telegram** | `agentforge telegram --agent-dir agents/lab-ops` (token via `--token` or `TELEGRAM_BOT_TOKEN`) | `agentforge.channels.telegram:run_polling` | Bot messaging |

MCP can also run over HTTP/SSE (`--transport http`), and the project ships a `.mcp.json` snippet for wiring `agentforge mcp` into Claude Code.

## Key Concepts

### Agent Spec (`agent.yaml`)

Every agent is born from a spec. The spec defines:
- **Identity**: ID, name, purpose
- **Persona**: tone, style, personality
- **Tools**: named tools with description and `when_to_use` / `when_not_to_use` decision hints (injected into the tool schema)
- **Memory**: type (`none` / `session_summary`), max turns, policy (`truncate` / `summarize`)
- **Guardrails**: `must` rules (compliance-checked with correction retries) and `must_not` rules (auto-corrected after output)
- **Workflow**: mode, max tool cycles, reflection rounds, worker agents for delegation
- **Deployment**: provider (`ollama` default; `mock` for tests) and default/fallback models

### Tool Calling

In `respond_or_tool` mode, each cycle is one provider inference with the tool schema:
1. Model decides: direct response **or** tool call
2. Tool call → executed → result injected → next cycle
3. **Loop guard**: aborts when the same (tool, args, result) triple repeats in a sliding window of 5
4. **Pushback**: if the model responds without tools (while tools are available and none have run yet), it gets up to 2 redirects to use them
5. On exhausting `max_tool_cycles` → final inference with all accumulated results

### Multi-Agent

An orchestrator agent declares workers in `workflow.agents`. The engine injects `run_agent` into the tool schema listing those workers — the model decides when and to whom to delegate, and workers run through their own `AgentRuntime` lifecycle.

### Tool Registry (Voyager Pattern)

Agents can create new Python tools at runtime: write implementation → write tests → `run_bash` pytest → `register_tool_file` (validates, copies to `tool_registry/`, updates `registry.yaml`). Registered tools are loaded by the dynamic loader and become available to all agents in the next session.

## Project Structure

```
agents-framework/
├── agents/                    # Agent definitions (each self-contained)
├── tool_registry/             # Dynamically registered tools
├── src/agentforge/
│   ├── channels/              # CLI, HTTP, MCP, Telegram
│   ├── providers/             # Ollama, LlamaCpp, Mock
│   ├── runtime/               # AgentRuntime engine, memory
│   ├── tools/                 # Built-in tools, registry, dynamic loader
│   ├── core/                  # AgentSpec Pydantic models, validation
│   ├── generators/            # Artifact generation from specs
│   ├── eval/                  # LLM judge scoring
│   ├── wizard/                # Interactive spec creation
│   └── research/              # Vault utilities
├── tests/                     # Test suite (MockProvider, no Ollama needed)
├── finetune/                  # Fine-tuning pipeline
├── scripts/                   # Benchmark runner
├── docs/                      # Architecture, PRD, strategy docs
└── openwiki/                  # Generated documentation (this wiki)
```

## Where to Go Next

| You want to… | Read |
|--------------|------|
| Understand the overall architecture, the channel → runtime → provider/tool topology, and the spec-first + local-first design principles | [Architecture Overview](./architecture/overview.md) |
| Learn the `AgentSpec` Pydantic model hierarchy, spec validation, the wizard flow, and artifact generation (`system_prompt.md`, `runtime.yaml`, `tools.yaml`, `eval.yaml`, `README.md`) | [Spec System](./architecture/spec-system.md) |
| Follow the end-to-end lifecycle of `AgentRuntime.run()`: input rule injection → tool calling cycle → guardrails → reflection → memory persistence → `runs.jsonl` logging | [Execution Pipeline](./workflows/execution-pipeline.md) |
| See how orchestrator agents delegate to workers via the auto-injected `run_agent` tool | [Multi-Agent Orchestration](./workflows/multi-agent-orchestration.md) |
| Walk through the Voyager self-registration flow step by step | [Tool Self-Registration](./workflows/tool-self-registration.md) |
| Compare LLM backends (Ollama, LlamaCpp, Mock) and the four channel implementations in depth | [Providers & Channels](./integrations/providers-channels.md) |
| Learn the global tool registry, built-in tool catalogue, dynamic loading, and `register_tool_file` | [Tool System](./tools/tool-system.md) |
| Browse the agent catalogue, the 4-stage certification funnel, reference/benchmark/specialized agents, and the agent mesh | [Agent Domains](./domain/agents.md) |
| Use the `agentforge eval` CLI, the LLM judge, benchmark runners, and the LoRA fine-tuning pipeline | [Evaluation & Finetuning](./operations/eval-finetune.md) |
