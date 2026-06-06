# Skill Generator

**ID:** `real-p4`  
**Spec version:** 0.1

## Purpose

Generates complete and actionable skills for Claude Code from descriptions. Produces ready-to-use technical documentation with valid YAML frontmatter.

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
