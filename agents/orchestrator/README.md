# Orquestrador

**ID:** `orchestrator`  
**Versão da spec:** 0.1

## Propósito

Analisa pedidos complexos, decompõe em subtarefas e delega para agentes especializados. Sintetiza os resultados em uma resposta coesa.

## Configuração

| Campo              | Valor                          |
|--------------------|--------------------------------|
| Canal              | cli            |
| Modelo padrão      | qwen3.5:9b |
| Modelo fallback    | —                     |
| Workflow           | respond_or_tool           |
| Memória            | desabilitada                  |
| Tools              | Nenhuma                   |
| Saída              | text             |

## Arquivos gerados

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
