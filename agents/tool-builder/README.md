# Tool Builder

**ID:** `tool-builder`  
**Spec version:** 0.1

## Purpose

Creates functional Python tools from a description, tests them with pytest, and registers them in the AgentForge tool_registry/ for immediate use by other agents. Every created tool becomes permanently available in the framework.


## Configuration

| Field              | Value                          |
|--------------------|--------------------------------|
| Channel            | cli            |
| Default model      | qwen3.5:27b |
| Fallback model     | —                     |
| Workflow           | respond_or_tool           |
| Memory             | disabled                  |
| Tools              | `write_file`, `read_file`, `run_bash`, `register_tool_file`                   |
| Output             | text             |

## Generated files

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
