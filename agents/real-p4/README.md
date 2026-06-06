# Skill Generator

**ID:** `real-p4`  
**Versão da spec:** 0.1

## Propósito

Gera skills completas e acionáveis para Claude Code a partir de descrições. Produz documentação técnica pronta para uso com frontmatter YAML válido.

## Configuração

| Campo              | Valor                          |
|--------------------|--------------------------------|
| Canal              | cli            |
| Modelo padrão      | qwen3.5:27b |
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
