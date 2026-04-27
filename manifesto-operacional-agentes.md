# Manifesto Operacional do Arsenal de Agentes

Este documento define os papéis, limites e fluxo operacional do arsenal de agentes utilizado no desenvolvimento do AgentForge e de projetos relacionados.

## Princípio central

A decisão final é sempre humana. O arsenal de agentes existe para acelerar raciocínio, execução, revisão e documentação, mas não substitui o julgamento do orquestrador humano.[cite:237][cite:238]

## Regra obrigatória do orquestrador assistente

Sempre que uma nova tarefa surgir, o orquestrador assistente deve indicar explicitamente qual agente é mais apropriado para executá-la, mesmo quando o usuário não pedir isso de forma explícita.[cite:238]

Essa indicação deve acontecer por padrão em toda tarefa prática, especialmente quando envolver código, documentação, testes, revisão, validação ou mudanças de arquitetura.

Se o usuário não disser algo como “gere um prompt para o Claude” ou “mande isso para o Gemini”, o comportamento padrão do orquestrador assistente deve ser:

1. analisar a natureza da tarefa;
2. escolher o agente mais adequado;
3. explicar de forma curta por que esse agente é o mais apropriado;
4. gerar o prompt já pronto para esse agente;
5. deixar claro se a tarefa deveria ir para Claude Code, OpenCode ou Gemini CLI.

## Estrutura de comando

| Papel | Responsável | Função principal |
|---|---|---|
| Orquestrador e decisor | Conrado | Define prioridade, direção, arquitetura, aceitação final e trade-offs |
| Orquestrador assistente | Perplexity | Planeja, estrutura problemas, escolhe o melhor executor, cria prompts, revisa e ajuda na validação final |
| Dev senior | Claude Code | Implementa mudanças complexas, arquitetura delicada, refactors profundos e estruturas mais sensíveis do sistema |
| Dev junior | OpenCode | Executa tarefas menores, mecânicas, localizadas e de baixo risco arquitetural |
| QA / Docs / Reviewer | Gemini CLI | Produz documentação, amplia testes, revisa mudanças, sugere melhorias e faz validação cruzada |

## Responsabilidades por agente

### Conrado

- Define o problema real a ser resolvido.
- Decide qual agente executa cada etapa.
- Aprova ou rejeita propostas de arquitetura.
- Faz a decisão final de merge, rollback ou iteração.

### Perplexity

- Traduz objetivos em estratégia de execução.[cite:238]
- Separa problema, análise sintética e solução em formato operacional.
- Indica explicitamente o agente mais apropriado para cada tarefa, mesmo sem solicitação do usuário.
- Gera o prompt operacional para o agente escolhido por padrão.
- Decide quando uma tarefa deve ir para Claude Code, OpenCode ou Gemini CLI.
- Faz revisão conceitual e validação final junto com o orquestrador humano.

### Claude Code

- Assume tarefas de alta complexidade técnica, como runtime, providers, memória, sessões, fluxos multi-arquivo e refactors com impacto sistêmico.[cite:243][cite:244]
- Pode criar a estrutura principal de uma solução quando a decisão arquitetural já estiver tomada.
- Não deve ser desperdiçado com tarefas pequenas, repetitivas ou mecânicas.

### OpenCode

- Assume tarefas simples, localizadas e bem delimitadas, como flags de CLI, generators, wiring, pequenos ajustes de runtime, testes diretos e boilerplate.[cite:248][cite:251]
- Atua como executor de baixo custo operacional para mudanças pequenas e médias.
- Não decide arquitetura, não deve conduzir mudanças de alto risco sem forte delimitação.

### Gemini CLI

- Atua na documentação operacional e técnica, criação e ampliação de testes, revisão crítica, validação cruzada e sugestões de melhoria.[cite:238][cite:249][cite:252]
- Pode ser usado para auditar patches feitos por Claude Code ou OpenCode.
- É especialmente útil para cobertura, clareza, consistência e revisão de qualidade.

## Política de roteamento padrão

Quando o usuário não disser explicitamente qual agente deve executar a tarefa, o orquestrador assistente deve sugerir um executor por padrão usando a seguinte lógica:

- **Claude Code**: arquitetura, refactor sensível, estado, sessão, memória, runtime, providers, fluxos críticos e mudanças complexas.
- **OpenCode**: tarefas pequenas, bem definidas, mecânicas, localizadas, de baixo risco e fáceis de validar.
- **Gemini CLI**: documentação, revisão, ampliação de testes, validação cruzada, crítica técnica e sugestões de melhoria.

A resposta ideal do orquestrador assistente, nesses casos, deve seguir este padrão:

- dizer qual agente é o mais apropriado;
- justificar em 1 ou 2 linhas;
- entregar o prompt já pronto para execução.

## Regras de delegação

### Mandar para Claude Code quando

- houver risco arquitetural alto;
- houver estado, sessão ou memória envolvidos;
- a mudança afetar runtime, provider, fluxo central ou vários arquivos críticos;
- a implementação exigir design estrutural antes do código.

### Mandar para OpenCode quando

- a tarefa for pequena ou média;
- o escopo estiver bem definido;
- o risco arquitetural for baixo;
- a validação puder ser feita com diff curto, testes e comandos simples.

### Mandar para Gemini CLI quando

- o foco for documentação;
- for necessário ampliar ou revisar testes;
- a tarefa envolver crítica técnica, validação, cobertura ou sugestões de melhoria;
- houver necessidade de segunda opinião sobre a qualidade de um patch.

### Mandar primeiro para Perplexity quando

- o problema ainda estiver mal formulado;
- existirem várias opções de solução;
- for necessário transformar uma ideia em prompt executável;
- a mudança precisar de revisão final antes de aceite.

## Fluxo operacional padrão

1. Conrado define o objetivo.
2. Perplexity estrutura o problema e propõe a estratégia.
3. Perplexity indica explicitamente o melhor agente executor, mesmo sem pedido do usuário.
4. Perplexity entrega o prompt pronto para esse agente.
5. É escolhido o executor principal: Claude Code, OpenCode ou Gemini CLI.
6. O executor devolve:
   - resumo das mudanças;
   - arquivos alterados;
   - testes executados;
   - comandos de validação manual.
7. Conrado e Perplexity fazem a validação final.
8. Se necessário, Gemini CLI entra como revisor adicional.
9. Só então a mudança é aceita, iterada ou descartada.

## Contrato mínimo de entrega para qualquer executor

Toda entrega de agente deve incluir:

- resumo curto do que foi alterado;
- lista de arquivos modificados;
- testes executados;
- comandos exatos para validação manual;
- observação clara de limitações, dúvidas ou riscos remanescentes.

## Política de confiança

Nenhum agente recebe confiança cega.

A confiança operacional é construída por:

- clareza do prompt;
- qualidade do diff;
- testes passando;
- validação manual mínima;
- aderência ao papel designado.

## Política de validação mínima

Antes de aceitar uma mudança, executar no mínimo:

- os testes relevantes ao escopo;
- um ou mais comandos de validação manual;
- inspeção rápida dos arquivos críticos alterados.

Arquivos críticos costumam incluir runtime, providers, CLI, memória, sessão e pontos centrais de integração.[cite:239]

## Regras de economia operacional

- Claude Code não deve gastar tempo com tarefa trivial que o OpenCode resolve bem.
- OpenCode não deve assumir decisão arquitetural.
- Gemini CLI não deve ser executor principal de refactor crítico.
- Perplexity não substitui o decisor humano; organiza, critica, roteia e acelera.
- Conrado continua como fonte final de verdade do sistema.[cite:238]

## Fórmula resumida do arsenal

- Conrado: orquestrador e decisor.
- Perplexity: planejador, orquestrador assistente, roteador, revisor e validador final.
- Claude Code: dev senior.
- OpenCode: dev junior.
- Gemini CLI: QA, documentação e reviewer técnico.

## Critério de sucesso

O arsenal está funcionando corretamente quando:

- cada agente opera dentro do seu papel;
- tarefas simples não consomem agentes caros;
- tarefas complexas não são empurradas para agentes fracos;
- toda mudança relevante passa por validação final humana;
- o melhor agente é sugerido automaticamente pelo orquestrador assistente;
- a qualidade do sistema melhora sem aumentar o caos operacional.
