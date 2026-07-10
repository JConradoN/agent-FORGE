# Agent Spec System

## Overview

Every agent in AgentForge is defined by a single source of truth: **`agent.yaml`**. This spec drives artifact generation, runtime behavior, tool availability, guardrail enforcement, evaluation, and memory policy. No behavior exists outside the spec.

## Spec File Locations

| File | Role |
|------|------|
| `agent.yaml` | Primary spec — Pydantic `AgentSpec` model. Validated at runtime. |
| `runtime.yaml` | Generated config — `RuntimeConfig` model. Provider, model, workflow params. |
| `system_prompt.md` | Generated — structured prompt built from spec fields. |
| `tools.yaml` | Generated — tool schema list. |
| `eval.yaml` | Generated — evaluation configuration. |
| `README.md` | Generated — agent technical documentation. |

The `generate` CLI command produces all derived files from `agent.yaml`.

## AgentSpec Data Model

Defined in `src/agentforge/core/agent_models.py`. Key fields:

### AgentIdentity
| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier (e.g., `forge-f3`, `lab-ops`) |
| `name` | `str` | Display name (e.g., "Market Analyst") |
| `purpose` | `str` | Free-text description of the agent's job |

### Persona
| Field | Type | Description |
|-------|------|-------------|
| `tone` | `str` | Communication tone (e.g., "technical", "friendly") |
| `style` | `str` | Writing style (e.g., "objective and analytical") |
| `personality` | `str \| None` | Optional personality trait |

### ToolSpec
| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Tool name — must match a registered tool |
| `required` | `bool` | Whether the agent MUST use this tool |
| `description` | `str \| None` | Tool description |
| `category` | `str \| None` | Tool category |
| `status` | `str` | `stable` \| `optional` \| `experimental` |
| `when_to_use` | `str \| None` | Decision hint injected into tool description |
| `when_not_to_use` | `str \| None` | Negative hint for the model |
| `input_schema` | `str \| None` | JSON schema string for tool arguments |
| `output_schema` | `str \| None` | JSON schema string for expected output |

### MemorySpec
| Field | Type | Description |
|-------|------|-------------|
| `type` | `str` | Memory type: `none`, `session_summary` |
| `enabled` | `bool` | Whether memory is active |
| `max_turns` | `int` | Conversation turns to keep (0 = unlimited) |
| `policy` | `str` | `truncate` (discard oldest) or `summarize` (compress to summary) |

### GuardrailSpec
| Field | Type | Description |
|-------|------|-------------|
| `must` | `list[str]` | Rules that MUST be satisfied (checked via phrase match or LLM judge) |
| `must_not` | `list[str]` | Rules that must NOT be violated (checked via LLM judge) |
| `optional` | `list[str]` | Soft guidelines |

### WorkflowSpec
| Field | Type | Description |
|-------|------|-------------|
| `mode` | `str` | `respond_or_tool` (tool calling) or other modes |
| `multi_turn` | `bool` | Whether to persist conversation history |
| `max_tool_cycles` | `int` | Max rounds of tool calling (default 3) |
| `reflection_rounds` | `int` | Rounds of self-critique after output (default 0) |
| `agents` | `list[AgentRef]` | Workers available for delegation via `run_agent` |

### AgentRef (for multi-agent)
| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Worker agent name |
| `agent_dir` | `str` | Directory path to worker's `agent.yaml` |
| `description` | `str \| None` | Description for tool schema |

### DeploymentSpec & ModelPolicySpec
| Field | Type | Description |
|-------|------|-------------|
| `provider` | `str` | LLM provider: `ollama`, `llamacpp`, `mock` |
| `default_model` | `str` | Default model (e.g., `qwen3.5:27b`) |
| `fallback_model` | `str \| None` | Fallback model |

## Validation

Validation is done via Pydantic models with `extra="forbid"` — unknown fields cause validation errors.

- **`validate_agent_spec(path)`** — validates a single `agent.yaml`
- **`validate_all_specs(root)`** — validates framework-level specs in `specs/` directory
- **`save_agent_spec(path, spec)`** — serializes a validated spec back to YAML

The CLI `agentforge validate` command uses `validate_all_specs()` to check all framework specs.

## Artifact Generation

The `generate` CLI command calls `generate_agent_files()` in `src/agentforge/generators/agent_files.py`:

1. **`build_system_prompt(spec)`** — constructs a structured Markdown prompt with identity, objective, persona, guardrails, tools, memory policy, output format, and model/workflow policy.
2. **`build_runtime_config(spec)`** — flattens nested spec fields into `RuntimeConfig` dict.
3. **`build_eval_config(spec)`** — creates evaluation configuration with metrics.
4. **`build_tools_config(spec)`** — serializes tool list into `tools.yaml` format.
5. **`build_agent_readme(spec)`** — creates a technical README with agent summary.

Generated files are written to the same directory as `agent.yaml`.

## Runtime Config Overrides

The `RuntimeConfig` model in `engine.py` supports environment variable overrides:

| Env Var | Overrides |
|---------|-----------|
| `AGENTFORGE_PROVIDER` | `deployment.provider` |
| `AGENTFORGE_MODEL` | `model_policy.default_model` |

These override values from `runtime.yaml` at initialization time.

## Source References

| File | Role |
|------|------|
| `src/agentforge/core/agent_models.py` | All Pydantic spec models |
| `src/agentforge/core/validation.py` | `load_yaml_file`, `validate_agent_spec`, `validate_all_specs`, `save_agent_spec` |
| `src/agentforge/core/models.py` | `FrameworkSpec`, `OrchestratorSpec`, `ValidationResult` |
| `src/agentforge/generators/agent_files.py` | All artifact builders |
| `src/agentforge/runtime/engine.py` | `RuntimeConfig` — runtime config model with env var overrides |
| `src/agentforge/wizard/flow.py` | Interactive spec creation wizard |
