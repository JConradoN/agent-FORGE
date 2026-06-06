# Orchestrator

**ID:** `orchestrator`  
**Spec version:** 0.1

## Purpose

Analyzes complex requests, decomposes them into subtasks, and delegates to specialized agents. Synthesizes the results into a cohesive response.

## Configuration

| Field              | Value                          |
|--------------------|--------------------------------|
| Channel            | cli            |
| Default model      | qwen3.5:9b |
| Fallback model     | —                     |
| Workflow           | respond_or_tool           |
| Memory             | disabled                  |
| Tools              | None                   |
| Output             | text             |

## Generated files

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
