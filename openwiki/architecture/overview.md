# Architecture Overview

## High-Level Design

AgentForge is a spec-first agent orchestration framework. The architecture follows a clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                   User / Channel                         │
│  CLI ── HTTP ── MCP ── Telegram                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              CLI / Channel Entrypoints                   │
│  agentforge run│serve│mcp│telegram                       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              AgentRuntime (engine.py)                    │
│                                                          │
│  1. Load agent.yaml + runtime.yaml                      │
│  2. Build tools schema                                   │
│  3. Apply memory policy                                  │
│  4. Run tool calling cycle (with loop guard)            │
│  5. Check guardrails (must_not + must)                  │
│  6. Apply reflection (if configured)                    │
│  7. Save history + return result                        │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Provider │ │  Tools   │ │  Memory  │
   │  Ollama  │ │Registry  │ │History   │
   │ LlamaCpp │ │Dynamic   │ │Mem0Hook  │
   │  Mock    │ │Loader    │ │          │
   └──────────┘ └──────────┘ └──────────┘
```

## Core Components

### 1. AgentSpec System

**Location**: `src/agentforge/core/agent_models.py`

The AgentSpec is a Pydantic model that defines everything about an agent. It uses `extra="forbid"` — unknown fields cause validation errors. This ensures the spec is always the single source of truth.

The spec drives:
- System prompt generation
- Runtime configuration
- Tool schema construction
- Guardrail enforcement
- Memory policy
- Evaluation criteria

### 2. Runtime Engine

**Location**: `src/agentforge/runtime/engine.py`

The `AgentRuntime` class implements the full execution pipeline:

```
from_agent_dir(agent_dir) → AgentRuntime
    ├── Validates agent.yaml → AgentSpec
    ├── Loads runtime.yaml → RuntimeConfig
    ├── Loads tools.yaml → list[ToolSpec]
    ├── Loads history.json (if memory enabled)
    │
    └── run(input_text) → Result
        ├── Build system prompt
        ├── Tool calling cycle (loop guard + pushback)
        ├── Guardrails check (must_not auto-correct + must compliance)
        ├── Reflection rounds
        ├── Save history
        └── Return {agent_id, output, metadata}
```

Key design decisions:
- **Pushback**: If the model responds without tools when tools are available, the engine pushes back (up to 2 redirects) before returning the raw response.
- **Loop guard**: Tracks recent (tool, args, result) triplets. Aborts after 5 identical calls+results.
- **Regex fallback**: If Ollama doesn't return tool_calls in the API response but the text contains tool call patterns, the regex parser extracts them.
- **Final inference**: When cycles are exhausted, the model produces a final response based on accumulated tool evidence, not raw tool output.

### 3. Provider Abstraction

**Location**: `src/agentforge/providers/`

All providers implement `BaseProvider.generate(ProviderRequest) → ProviderResponse`. This abstraction allows:
- Swapping backends (Ollama → LlamaCpp → Mock)
- Testing without external dependencies
- Future providers (Gemini, OpenAI, etc.)

The provider registry supports dynamic registration: `registry.register(name, ProviderClass)`.

### 4. Tool Registry

**Location**: `src/agentforge/tools/registry.py`

A global dict `_ToolRegistry` stores all callable tools. Built-in tools are auto-registered at startup. Dynamic tools (from `tool_registry/`) are loaded after builtins.

Tools are exposed to the model via OpenAI-style function schemas, built from `ToolSpec` definitions in the agent spec.

### 5. Memory System

**Location**: `src/agentforge/runtime/memory.py`

Supports two policies:
- **truncate**: Removes oldest turns, keeps last N * 2 messages.
- **summarize**: Compresses overflow turns into a summary message. Supports custom LLM-based summarizers via `mem0_hook.py`.

Summary messages use a special prefix (`Resumo da conversa anterior:`) for identification.

## Data Flow

### Agent Creation Flow

```
agentforge wizard → agent.yaml
agentforge generate → system_prompt.md + runtime.yaml + tools.yaml + eval.yaml + README.md
agentforge run → AgentRuntime.run() → Provider.generate() → Tool execution
```

### Multi-Agent Flow

```
Orchestrator receives task
    → Model decides to delegate → calls run_agent(agent_dir, input)
    → Engine loads worker's agent.yaml + runtime.yaml
    → Engine runs worker with input
    → Worker output injected into orchestrator's history
    → Orchestrator synthesizes results
```

### Tool Self-Registration Flow (Voyager)

```
Agent writes implementation.py (write_file)
    → Agent writes test_implementation.py (write_file)
    → Agent runs pytest (run_bash)
    → Agent calls register_tool_file
        → Validates file
        → Copies to tool_registry/
        → Updates registry.yaml
        → Tool available to all agents
```

## Key Design Principles

1. **Spec-first**: No behavior exists outside the YAML spec.
2. **Local-first**: Optimized for Ollama. Cloud providers are secondary.
3. **Deterministic guardrails**: `must` rules are checked via both deterministic text search and LLM judgment.
4. **Model-agnostic providers**: The provider abstraction makes backend changes transparent.
5. **Voyager pattern**: Agents can create their own tools, enabling emergent capability growth.
6. **4-channel flexibility**: The same agent runs on CLI, HTTP, MCP, and Telegram without spec changes.

## Source Map

| Component | Primary File |
|-----------|-------------|
| Spec models | `src/agentforge/core/agent_models.py` |
| Validation | `src/agentforge/core/validation.py` |
| Runtime engine | `src/agentforge/runtime/engine.py` |
| Memory management | `src/agentforge/runtime/memory.py` |
| Provider interface | `src/agentforge/providers/base.py` |
| Provider registry | `src/agentforge/providers/registry.py` |
| Ollama provider | `src/agentforge/providers/ollama.py` |
| LlamaCpp provider | `src/agentforge/providers/llamacpp.py` |
| Mock provider | `src/agentforge/providers/mock.py` |
| Tool registry | `src/agentforge/tools/registry.py` |
| Dynamic loader | `src/agentforge/tools/dynamic_loader.py` |
| Tool registration | `src/agentforge/tools/register_tool_file.py` |
| Artifact generation | `src/agentforge/generators/agent_files.py` |
| CLI entrypoint | `src/agentforge/cli/main.py` |
| HTTP channel | `src/agentforge/channels/http.py` |
| MCP channel | `src/agentforge/channels/mcp_server.py` |
| Telegram channel | `src/agentforge/channels/telegram.py` |
| Evaluation judge | `src/agentforge/eval/judge.py` |
| Benchmark runner | `scripts/run_benchmark_eval.py` |
