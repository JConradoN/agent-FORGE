# AgentForge — Quick Start

**AgentForge** is a Python **spec-first**, **local-first** framework for creating and running LLM agents on-premise. Its core thesis, validated across 4 months of benchmarking 19 models, is:

> **TESTE-CI-PR-CLAUDE 2026-07-10: linha temporária pra validar o workflow de PR automático.**

The quality of a local agent depends more on how the runtime manages context, tool use decisions, guardrails, and evaluation than on the model itself.

## What This Wiki Covers

AgentForge is an agent orchestration framework with the following capabilities:

| Capability | Details |
|------------|---------|
| **Spec-driven agents** | Every agent is defined by an `agent.yaml` — no hidden behavior |
| **Tool calling** | Model-driven tool use via OpenAI/Ollama protocol with loop guards |
| **Multi-agent orchestration** | Agents delegate to workers via `run_agent` tool |
| **Active guardrails** | Auto-corrects violations of `must` and `must_not` rules |
| **Autonomous reflection** | N rounds of self-critique after output |
| **4 execution channels** | CLI, HTTP (n8n), MCP (Claude Code), Telegram |
| **Tool registry** | Agents create and register new Python tools at runtime (Voyager pattern) |
| **Evaluation** | Dataset-based eval + LLM judge scoring |
| **Finetuning** | LoRA fine-tuning pipeline with synthetic data generation |

## Getting Started

### Prerequisites

- Python 3.11+
- Ollama installed and running (`docker compose` or local)
- Recommended model: `qwen3.5:9b` (simple) or `qwen3.5:27b` (complex)

### Installation

```bash
git clone <repo-url>
cd agents-framework
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Create Your First Agent

**Step 1 — Generate the spec:**

```bash
agentforge wizard
```

This creates `agents/<id>/agent.yaml` with persona, tools, memory, and guardrails.

**Step 2 — Generate artifacts:**

```bash
agentforge generate --path agents/<id>/agent.yaml
```

Produces: `system_prompt.md`, `runtime.yaml`, `tools.yaml`, `eval.yaml`, `README.md`.

**Step 3 — Run the agent:**

```bash
agentforge run --agent-dir agents/lab-ops --input "How is the server?"
```

Output in JSON (`--mode raw`) or human-readable text (`--mode pretty`).

## Execution Channels

The same agent spec runs on four channels:

| Channel | Command | Use Case |
|---------|---------|----------|
| **CLI** | `agentforge run --agent-dir agents/lab-ops --input "text"` | Direct interaction |
| **HTTP** | `agentforge serve --agent-dir agents/lab-ops --port 8080` | n8n / automation integration |
| **MCP** | `agentforge mcp --transport stdio` | Claude Code / Claude Desktop |
| **Telegram** | `agentforge telegram --agent-dir agents/lab-ops` | Bot messaging |

## Key Concepts

### Agent Spec (`agent.yaml`)

Every agent is born from a spec. The spec defines:
- **Identity**: ID, name, purpose
- **Persona**: Tone, style, personality
- **Tools**: List of tools with descriptions, decision hints
- **Memory**: Type (none/session_summary), max turns, policy (truncate/summarize)
- **Guardrails**: `must` rules (checked deterministically or via LLM judge), `must_not` rules (auto-corrected)
- **Workflow**: Mode, max tool cycles, reflection rounds, worker agents for delegation

### Tool Calling

In `respond_or_tool` mode:
1. Inference with tool schema (OpenAI/Ollama protocol)
2. Model decides: direct response or tool call
3. If tool call → execute → inject result → next cycle
4. **Loop guard**: aborts if the same tool call + result repeats 5 consecutive times
5. **Pushback**: if the model responds without tools (when tools are available), it gets 2 chances to use them
6. On exhausting cycles → final inference with all accumulated results

### Multi-Agent

An orchestrator agent declares workers in `workflow.agents`. The engine injects `run_agent` into the tool schema. The model decides when and to whom to delegate.

### Tool Registry (Voyager Pattern)

Agents can create new Python tools at runtime:
1. Write implementation via `write_file`
2. Write tests via `write_file`
3. Run pytest via `run_bash`
4. Call `register_tool_file` to copy and register the tool

Registered tools become available to all agents permanently.

## Project Structure

```
agents-framework/
├── agents/                    # Agent definitions (each self-contained)
├── tool_registry/             # Dynamically registered tools
├── src/agentforge/
│   ├── channels/              # CLI, HTTP, MCP, Telegram
│   ├── providers/             # Ollama, LlamaCpp, Mock
│   ├── runtime/               # Engine, memory, mem0 hook
│   ├── tools/                 # Built-in tools, registry, dynamic loader
│   ├── core/                  # AgentSpec Pydantic models, validation
│   ├── generators/            # Artifact generation from specs
│   ├── eval/                  # LLM judge scoring
│   ├── wizard/                # Interactive spec creation
│   └── research/              # Vault utilities
├── tests/                     # 278 tests (MockProvider, no Ollama needed)
├── finetune/                  # Fine-tuning pipeline (V3)
├── scripts/                   # Benchmark runner
├── docs/                      # Architecture, PRD, strategy docs
└── openwiki/                  # Generated documentation (this wiki)
```

## Where to Go Next

- **[Architecture Overview](./architecture/overview.md)** — System design and component relationships
- **[Spec System](./architecture/spec-system.md)** — AgentSpec Pydantic models and validation
- **[Execution Pipeline](./workflows/execution-pipeline.md)** — Runtime engine lifecycle
- **[Providers & Channels](./integrations/providers-channels.md)** — LLM backends and execution interfaces
- **[Tool System](./tools/tool-system.md)** — Registry, built-in tools, Voyager pattern
- **[Agent Domains](./domain/agents.md)** — Agent types, the 4-stage funnel, agent mesh
- **[Evaluation & Finetuning](./operations/eval-finetune.md)** — Benchmark, eval, training pipeline
