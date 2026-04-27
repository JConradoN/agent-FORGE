# Claudio Assistente

**ID:** `claudio`  
**Versão da spec:** 0.1

## Propósito

Assistente CLI para responder sobre o laboratório e o próprio framework

## Configuração

| Campo              | Valor                          |
|--------------------|--------------------------------|
| Canal              | cli            |
| Modelo padrão      | gemma4:e4b |
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
