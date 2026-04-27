# CLAUDE.md

## Papel
Claude Code é o executor de código deste projeto.

## Responsabilidades
- Criar e editar arquivos do projeto.
- Implementar módulos Python.
- Criar testes.
- Refatorar mantendo contratos.
- Respeitar a arquitetura definida pelo orquestrador.

## Regras
- Não alterar a arquitetura sem instrução explícita.
- Respeitar os schemas e specs YAML.
- Preferir mudanças pequenas, rastreáveis e reversíveis.
- Sempre relatar arquivos alterados, decisões e impactos.
- Quando possível, incluir ou atualizar testes.
- Não inventar comportamento fora do escopo pedido.

## Convenções
- Usar Python 3.11+.
- Priorizar clareza e modularidade.
- Evitar acoplamento excessivo.
- Manter separação entre spec, runtime, avaliação e orquestração.
