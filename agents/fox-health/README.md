# Fox Health Monitor

**ID:** `fox-health`  
**Versão da spec:** 0.1

## Propósito

Agente de diagnóstico de saúde do sistema fox-server - analisa CPU, memória, disco, GPU e processos

## Configuração

| Campo              | Valor                          |
|--------------------|--------------------------------|
| Canal              | cli            |
| Modelo padrão      | gemma4:e4b |
| Modelo fallback    | —                     |
| Workflow           | respond_or_tool           |
| Memória            | desabilitada                  |
| Tools              | `collect_system_health`                   |
| Saída              | text             |

## Arquivos gerados

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
