# Tool Builder

**ID:** `tool-builder`  
**Versão da spec:** 0.1

## Propósito

Cria tools Python funcionais a partir de uma descrição, testa com pytest, e as registra no AgentForge tool_registry/ para uso imediato por outros agentes. Toda tool criada fica disponível permanentemente no framework.


## Configuração

| Campo              | Valor                          |
|--------------------|--------------------------------|
| Canal              | cli            |
| Modelo padrão      | qwen3.5:27b |
| Modelo fallback    | —                     |
| Workflow           | respond_or_tool           |
| Memória            | desabilitada                  |
| Tools              | `write_file`, `read_file`, `run_bash`, `register_tool_file`                   |
| Saída              | text             |

## Arquivos gerados

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
