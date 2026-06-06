# Python Tool Developer

**ID:** `real-p3`  
**Spec version:** 0.1

## Purpose

Develops functional Python tools with type hints, docstrings, error handling, and pytest tests that actually pass.

## Configuration

| Field              | Value                          |
|--------------------|--------------------------------|
| Channel            | cli            |
| Default model      | qwen3.5:27b |
| Fallback model     | —                     |
| Workflow           | respond_or_tool           |
| Memory             | disabled                  |
| Tools              | `write_file`, `read_file`, `run_bash`                   |
| Output             | text             |

## Generated files

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
