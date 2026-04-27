# Contributing

## Objetivo

Este repositório existe para desenvolver e validar o AgentForge com foco em:

- agentes configuráveis por spec;
- uso prático de modelos locais e on-premise;
- memória, histórico e políticas de contexto controladas;
- criação guiada de agentes e tools;
- testes de eficácia e previsibilidade operacional.

A prioridade do projeto é evolução incremental, verificável e bem registrada.

## Princípios

- Fazer mudanças pequenas e testáveis.
- Commits devem representar mudanças reais.
- Evitar misturar refactor, feature, teste e documentação no mesmo commit quando isso prejudicar a leitura.
- Manter a árvore de trabalho limpa entre tarefas relevantes.
- Toda mudança funcional deve ser validada antes de commit, ao menos com teste direcionado ou verificação manual explícita.

## Convenção de commits

Usar Conventional Commits de forma simples:

- `feat:` nova funcionalidade.
- `fix:` correção de bug.
- `refactor:` mudança estrutural sem alterar comportamento esperado.
- `test:` criação ou ajuste de testes.
- `docs:` documentação.
- `chore:` manutenção, limpeza, arquivos auxiliares e tarefas operacionais.

Exemplos:

- `feat(runtime): add multi-turn conversation history`
- `feat(memory): add summarize policy for bounded history`
- `feat(wizard): support complex agents and rich tools`
- `test(memory): cover summarize accumulation behavior`
- `docs(repo): add operational manifesto`
- `chore: remove accidental file from repository root`

## Regra de commit

Fazer commit sempre que houver uma mudança real, coerente e minimamente validada.

Situações em que o commit deve acontecer:

- uma feature pequena foi concluída;
- uma correção foi validada;
- um bloco relevante de testes foi adicionado ou ajustado;
- uma atualização documental importante foi concluída;
- uma limpeza operacional relevante foi finalizada.

Evitar:

- acumular muitas horas de trabalho útil sem commit;
- deixar várias mudanças diferentes misturadas sem necessidade;
- encerrar o dia com alteração importante não versionada.

## Fluxo de trabalho

Sequência recomendada para mudanças normais:

1. Entender o problema e definir escopo curto.
2. Alterar apenas os arquivos necessários.
3. Rodar testes direcionados ou validação manual objetiva.
4. Revisar `git diff` e `git status`.
5. Fazer commit com mensagem clara.
6. Só então começar a próxima mudança.

Comandos úteis:

```bash
git status
git diff
git add -A
git commit -m "feat(...): descrição"
```

Quando necessário, usar `git add -p` para separar mudanças por intenção.

## Árvore limpa

Antes de iniciar uma nova tarefa relevante:

- verificar `git status`;
- confirmar que a árvore está limpa, ou entender exatamente o que está pendente.

Antes de encerrar uma sessão de trabalho:

- rodar `git status`;
- decidir conscientemente se falta commit.

## Validação mínima

Toda mudança deve ter algum nível de validação proporcional ao risco:

- mudança pequena de texto: revisão manual;
- mudança de geração/config: teste direcionado;
- mudança de runtime/provider/memory/wizard: testes automatizados relevantes;
- mudança de comportamento de agente: teste manual explícito e, quando possível, teste automatizado.

Sempre que aplicável, registrar no commit ou no PR local quais comandos foram usados para validar.

## Papéis dos agentes

Uso operacional recomendado neste repositório:

- **Perplexity**: orquestração, planejamento, validação final e definição do próximo melhor passo.
- **Claude Code**: implementação mais complexa, mudanças estruturais e decisões difíceis de arquitetura.
- **OpenCode**: tarefas menores, ajustes locais, documentação operacional, melhorias de UX e refactors simples.
- **Gemini CLI**: revisão, documentação, validação, crítica de lacunas e sugestões de melhoria.

O humano continua sendo o orquestrador final e responsável por:

- aprovar direção;
- executar comandos sensíveis;
- validar prioridade;
- decidir o que entra no repositório.

## Escopo de mudanças

Preferir mudanças pequenas e iterativas.

Boa prática:

- primeiro fazer a infraestrutura mínima funcionar;
- depois cobrir com testes;
- depois melhorar UX, docs e refinamentos.

Evitar grandes refactors fora do caminho crítico, a menos que haja ganho claro em simplicidade, segurança ou testabilidade.

## Documentação viva

Sempre que uma mudança alterar o modo de uso do projeto, avaliar se também é necessário atualizar:

- `README.md`
- `ROADMAP.md`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `opencode.md`
- manifestos e documentos operacionais

Documentação atrasada gera perda de contexto e piora o uso dos agentes.

## Objetivo de longo prazo

Construir um framework de agentes que seja:

- utilizável;
- testável;
- previsível;
- econômico;
- útil como laboratório e como portfólio.

Toda contribuição deve aproximar o repositório desse objetivo.
