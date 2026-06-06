# Market Analyst

**ID:** `forge-f3`  
**Spec version:** 0.1

## Purpose

Fetches exchange rates and crypto quotes via API, analyzes trends, and generates a report with recommendations. Notifies the result through Claudio.

## Configuration

| Field              | Value                          |
|--------------------|--------------------------------|
| Channel            | cli            |
| Default model      | qwen3.5:27b |
| Fallback model     | —                     |
| Workflow           | respond_or_tool           |
| Memory             | disabled                  |
| Tools              | `http_get`, `write_file`, `send_claudio`                   |
| Output             | text             |

## Generated files

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
