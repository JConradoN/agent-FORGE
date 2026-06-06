# Analista de Mercado

**ID:** `forge-f3`  
**Versão da spec:** 0.1

## Propósito

Busca cotações de câmbio e cripto via API, analisa tendências e gera relatório com recomendações. Notifica resultado pelo Claudio.

## Configuração

| Campo              | Valor                          |
|--------------------|--------------------------------|
| Canal              | cli            |
| Modelo padrão      | qwen3.5:9b |
| Modelo fallback    | —                     |
| Workflow           | respond_or_tool           |
| Memória            | desabilitada                  |
| Tools              | `http_get`, `write_file`, `send_claudio`                   |
| Saída              | text             |

## Arquivos gerados

- `agent.yaml`
- `system_prompt.md`
- `runtime.yaml`
- `eval.yaml`
- `tools.yaml`
- `README.md`
