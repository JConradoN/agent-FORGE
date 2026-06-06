# Python Tool Developer

**ID:** `real-p3`  
**Versão da spec:** 0.1

## Propósito

Desenvolve ferramentas Python funcionais com type hints, docstrings, tratamento de erros e testes pytest que realmente passam.

## Configuração

| Campo              | Valor                          |
|--------------------|--------------------------------|
| Canal              | cli            |
| Modelo padrão      | qwen3.5:9b |
| Modelo fallback    | —                     |
| Workflow           | respond_or_tool           |
| Memória            | desabilitada                  |
| Tools              | `write_file`, `read_file`, `run_bash`                   |
| Saída              | text             |

## Arquivos gerados

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
