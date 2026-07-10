# Agent Domains

## The Four-Stage Funnel

AgentForge was shaped by a 4-stage model certification funnel that ran for 4 months, evaluating 19 local models. Each stage was an elimination gate — not a comparison.

| Stage | Gate Question | Filter | Models Remaining |
|-------|--------------|--------|-----------------|
| **ABS** | Can it call tools at all? | Basic tool call capability | 19 → |
| **LOP** | Does it hold under real operational pressure? | Stress test under real conditions | → |
| **FORGE** | Can it function as an agent? Multi-turn, chained, autonomous? | Multi-agent autonomous work | 7 → |
| **REAL** | Does it work in production? Real browser, real tests, no shortcuts? | Real-world operational use | 4 → |
| **agent-FORGE** | Deploy | Runtime for proven models | 4 |

The models in production are not "the best on a leaderboard" — they are the ones that proved they can complete actual jobs end-to-end, on real hardware, with real tasks.

## Agent Types

### Reference Agents

#### lab-ops

**ID**: `lab-ops`
**Purpose**: Server health monitoring and log inspection in a laboratory environment.
**Model**: `qwen3.5:27b`
**Tools**: `collect_system_health` (mandatory), `read_log_tail`
**Memory**: `session_summary`, 6 turns, `summarize` policy
**Guardrails**: Must execute `collect_system_health` before health responses. Must not fabricate metrics or access files outside log directory.

This is the canonical reference agent — the one used to validate the framework's operational capabilities.

#### tool-builder

**Purpose**: Creates and registers new Python tools during execution.
**Pattern**: Voyager — agent writes implementation, writes tests, runs pytest, registers the tool.
**Model**: `qwen3.5:27b`

#### orchestrator

**ID**: `orchestrator`
**Purpose**: Analyzes complex requests, decomposes them into subtasks, and delegates to specialized agents.
**Workers**: `lab-ops` (server health monitoring)
**Memory**: None (single-turn synthesis)
**Reflection**: 1 round

## Benchmark Agents

### forge-f3

**ID**: `forge-f3`
**Name**: Market Analyst
**Purpose**: Searches for exchange rates and crypto quotes via API, analyzes trends, and generates reports with recommendations.
**Model**: `qwen3.5:27b`
**Tools**: `http_get` (for quotes), `write_file` (for reports), `send_claudio` (for notifications)
**Guardrails**: Must search real quotes before writing reports. Must include specific sections. Must end with `ANÁLISE CONCLUÍDA`.
**Workflow**: `max_tool_cycles: 12` (allows for multi-URL fetching)

### real-p3

**Purpose**: Python tool with real tests (REAL P3 benchmark).
**Focus**: Producing Python code with passing tests.

### real-p4

**Purpose**: Skill generator (REAL P4 benchmark).
**Focus**: Creating reusable skill artifacts.

## Specialized Agents

### claudio

The Claudio agent — acts as a Telegram notification bot that receives and relays messages between agents and users.

### fox-health

Infrastructure health monitoring agent.

### infra-specialist

Specialized infrastructure analysis agent.

### link-reader

Document/article reading and summarization agent.

### vault-pilot

Specialized agent for vault workspace operations. Uses `scan_directory` and `extract_file_content` tools from the vault utilities.

### wks-worker

**Location**: `agents/wks-worker/`
**Purpose**: Windows workstation agent for the fox-wks ecosystem.
**Spec**: `agent.yaml`, `runtime.yaml`, `system_prompt.md`
**Tools**: `collect_wks_health`, plus system tools via HTTP server
**Features**:
- PowerShell terminal server (`fox_terminal_server.py`)
- System tool server on port 8091 via FastAPI (15 tools)
- Image tool server with SDXL pipeline for face swap
- Runs on Windows 11

## Agent Mesh

Agents form a mesh through:
1. **Shared tool registry** — tools registered by one agent are available to all agents
2. **Shared memory** — `~/.agent-mesh/state.db` for cross-agent context sharing
3. **Multi-agent delegation** — orchestrators connect agents via `run_agent`
4. **Claudio bot** — Telegram notification relay between agents and users

## Agent Directory Structure

Each agent lives in its own directory under `agents/<id>/`:

```
agents/<id>/
├── agent.yaml          # Primary spec (Pydantic validated)
├── system_prompt.md    # Generated structured prompt
├── runtime.yaml        # Generated execution config
├── tools.yaml          # Generated tool schema
├── eval.yaml           # Generated evaluation config
├── README.md           # Generated documentation
├── history.json        # Persisted conversation history (if memory enabled)
└── eval_runs/          # Evaluation run results
    └── <timestamp>.jsonl
```

## Agent Creation Flow

```
agentforge wizard
    → Creates agents/<id>/agent.yaml interactively
    → Defines persona, tools, memory, guardrails, workflow

agentforge generate --path agents/<id>/agent.yaml
    → Generates system_prompt.md, runtime.yaml, tools.yaml, eval.yaml, README.md
    → All derived from the single agent.yaml spec

agentforge run --agent-dir agents/<id>
    → Validates agent.yaml at runtime
    → Creates AgentRuntime from the directory
    → Executes the full pipeline
```

## Source References

| File | Role |
|------|------|
| `agents/*/agent.yaml` | All agent specifications |
| `agents/wks-worker/` | Windows workstation agent ecosystem |
| `agents/wks-worker/agent.yaml` | WKS worker spec |
| `agents/wks-worker/runtime.yaml` | WKS worker runtime config |
| `agents/wks-worker/system_prompt.md` | WKS worker system prompt |
| `agents/wks-worker/fox_terminal_server.py` | PowerShell terminal server |
| `agents/wks-worker/system_tool_server.py` | System tool server (port 8091, 15 tools) |
| `agents/wks-worker/image_tool_server.py` | Image generation with SDXL pipeline |
| `docs/fox-wks.md` | Fox-wks documentation |
| `docs/MODEL-STRATEGY.md` | Empirical model selection criteria |
