# Fox Health Monitor

**ID:** `fox-health`  
**Spec version:** 0.1

## Purpose

Diagnostic agent for fox-server system health - analyzes CPU, memory, disk, GPU, and processes

## Configuration

| Field              | Value                          |
|--------------------|--------------------------------|
| Channel            | cli            |
| Default model      | gemma4:e4b |
| Fallback model     | —                     |
| Workflow           | respond_or_tool           |
| Memory             | disabled                  |
| Tools              | `collect_system_health`                   |
| Output             | text             |

## Generated files

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
