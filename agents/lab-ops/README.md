# lab-ops — Reference Agent

Operational agent for server health monitoring and log inspection in a laboratory environment. It is the reference agent for AgentForge — it implements all framework mechanisms and serves as a baseline for validation and benchmarks.

---

## Configuration

| Field | Value |
|---|---|
| Model | `qwen3.5:9b` |
| Provider | `ollama` |
| Mode | `respond_or_tool` |
| Max tool cycles | 3 |
| Memory | `session_summary`, 6 turns |

---

## Tools

| Tool | Mandatory | Usage |
|---|---|---|
| `collect_system_health` | Yes | CPU, RAM, disk, GPU, processes |
| `read_log_tail` | No | Last lines of a log file |

### Tool use decision

The model is instructed via `when_to_use` / `when_not_to_use`:

- `collect_system_health`: use when the user asks about system health, resources, or processes
- `read_log_tail`: use when the user asks about specific logs, errors, or recent events

---

## Guardrails

**Must (mandatory behaviors):**
- Always execute `collect_system_health` before responding about system health
- Provide objective recommendations based on data
- Use absolute paths or paths relative to the server for logs

**Must-not (actively verified prohibitions):**
- Invent metrics
- Access files outside the server's log directory
- Change any system file

The `must_not` guardrails are verified by the model itself after each output. If violated, the runtime automatically resends a correction prompt.

---

## Run

```bash
# Direct CLI
agentforge run --agent-dir agents/lab-ops --input "How is the server?"

# Readable mode
agentforge run --agent-dir agents/lab-ops --input "Are there errors in the logs?" --mode pretty

# HTTP API (for n8n or automations)
agentforge serve --agent-dir agents/lab-ops --port 8080

# Telegram Bot
export TELEGRAM_BOT_TOKEN="..."
agentforge telegram --agent-dir agents/lab-ops

# MCP Tools in Claude Code (.mcp.json already configured)
agentforge mcp --transport stdio
```

---

## Evaluate

```bash
agentforge eval \
  --agent-dir agents/lab-ops \
  --dataset agents/lab-ops/eval_dataset.yaml
```

The dataset (`eval_dataset.yaml`) contains 8 test cases covering:
- General system health inquiry
- Analysis of specific resource usage (CPU, RAM, GPU)
- Log inspection
- Process diagnosis
- Out-of-scope questions (should refuse or redirect)

Results saved in `agents/lab-ops/eval_runs/<timestamp>.jsonl`.

---

## File structure

```
agents/lab-ops/
├── agent.yaml         # Spec (source of truth)
├── system_prompt.md   # Generated prompt — do not edit manually
├── runtime.yaml       # Generated execution parameters
├── tools.yaml         # Generated tool schema
├── eval.yaml          # Generated evaluation configuration
├── eval_dataset.yaml  # 8 manually maintained test cases
├── history.json       # Multi-turn history (generated at runtime)
└── runs/
    └── runs.jsonl     # Execution log (append-only, generated at runtime)
```

---

## Why lab-ops is the reference agent

- **Covers all mechanisms**: model-driven tool calling, loop guard, active guardrails, reflection, multi-turn memory, logging, eval
- **Controlled domain**: local infra has verifiable state — easy to validate if the response is based on real data
- **Non-trivial guardrails**: `must_not: invent metrics` tests if the model hallucinates when tools fail
- **Structured eval dataset**: 8 cases with notes on expected behavior serve as a regression suite

---

## Regenerate artifacts

If `agent.yaml` is modified, regenerate the artifacts:

```bash
agentforge generate --path agents/lab-ops/agent.yaml
```

This updates `system_prompt.md`, `runtime.yaml`, `tools.yaml`, and `eval.yaml`. `eval_dataset.yaml` is manually maintained and is not overwritten.
