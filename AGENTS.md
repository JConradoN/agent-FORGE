# AGENTS.md

## Papel deste arquivo
Este arquivo define as regras de projeto para o OpenCode neste repositório.

Se existir `CLAUDE.md` no mesmo diretório, este arquivo tem precedência para o OpenCode.
O `CLAUDE.md` continua válido como instrução específica para Claude Code.

## Papel do OpenCode neste projeto
OpenCode é o executor de tarefas pequenas, locais e de baixo risco.

## Responsabilidades
- Implementar mudanças pequenas e bem delimitadas.
- Editar arquivos específicos com escopo controlado.
- Ajustar CLI, generators, wiring, configs e testes diretos.
- Corrigir problemas mecânicos sem alterar a arquitetura.
- Relatar com clareza o que mudou, o que foi testado e o que precisa de validação humana.

## Regras
- Não alterar arquitetura sem instrução explícita.
- Não assumir refactors profundos ou mudanças sistêmicas por conta própria.
- Preferir mudanças pequenas, rastreáveis, reversíveis e fáceis de revisar.
- Respeitar schemas, contratos, specs YAML e convenções já existentes.
- Sempre informar arquivos alterados, testes executados e comandos de validação manual.
- Quando a tarefa parecer maior ou mais arriscada do que o esperado, sinalizar que deveria ir para Claude Code.
- Não inventar comportamento fora do escopo pedido.

## Escopo ideal
- Flags e opções de CLI.
- Ajustes localizados em runtime.
- Pequenas alterações em generators.
- Atualização de arquivos YAML gerados.
- Testes unitários diretos e simples.
- Boilerplate e manutenção mecânica.

## Não é foco do OpenCode
- Redesenho arquitetural.
- Refactor crítico multi-módulo.
- Sessão, memória e estado complexos.
- Mudanças de provider com risco sistêmico.
- Decisão estrutural sem definição prévia do orquestrador.

## Convenções
- Usar Python 3.11+.
- Priorizar clareza, diffs curtos e baixo risco.
- Manter separação entre spec, runtime, avaliação e orquestração.
- Entregar sempre em formato operacional: resumo, arquivos alterados, testes e validação manual.

## Roteamento de tarefas
- Claude Code: arquitetura, refactor sensível, runtime central, providers, memória, sessão e mudanças complexas.
- OpenCode: tarefas pequenas, locais, mecânicas e de baixo risco.
- Gemini CLI: documentação, revisão crítica, ampliação de testes, validação cruzada e sugestões de melhoria.

## Formato esperado de resposta do OpenCode
Toda entrega deve incluir:
- resumo curto do que foi feito;
- lista de arquivos alterados;
- testes executados;
- comandos exatos para validação manual;
- riscos, limitações ou dúvidas restantes.

## Observação
Quando necessário, o OpenCode pode consultar os demais arquivos de contexto do projeto, mas deve operar sem contradizer `CLAUDE.md`, `GEMINI.md` e o manifesto operacional definido pelo repositório.
