# AgentForge — PRD (retroativo)

## 1. Contexto e Motivação
O AgentForge nasceu da necessidade de operar agentes inteligentes em infraestrutura local (on-prem), eliminando a dependência crítica e financeira de APIs proprietárias. O projeto surge para provar que, com o arcabouço (harness) correto, modelos locais executados via Ollama podem ser tão eficazes em tarefas operacionais quanto modelos "frontier", com a vantagem da privacidade total e custo zero de execução.

## 2. Problema
A execução de agentes LLM em modelos menores (4B a 14B) enfrenta obstáculos que o AgentForge visa resolver:
- **Entropia de Contexto:** Históricos longos degradam rapidamente a lógica de modelos locais.
- **Inconsistência em Tools:** Modelos menores frequentemente alucinam argumentos de ferramentas ou ignoram restrições.
- **Dependência de Frontier Models:** A percepção de que apenas modelos como Claude ou GPT-4 podem ser agentes úteis, ignorando o potencial de modelos locais bem guiados.

## 3. Tese / Visão
**"20% modelo, 80% runtime."**
A tese central é que o sucesso de um agente local não depende de aumentar o número de parâmetros do modelo, mas de fornecer um runtime rigoroso, memória controlada e ferramentas ricas em metadados. O foco é reduzir a dependência mental e prática de provedores únicos, tratando modelos externos (Claude, Gemini, GPT) como upgrades opcionais e não como requisitos obrigatórios.

## 4. O Ecossistema de Orquestração
O AgentForge é uma peça central em um ecossistema de ferramentas complementares:
- **Perplexity:** Orquestrador *human-in-the-loop* para planejamento de alto nível, decisão e validação de fatos.
- **Gemini CLI:** Especialista em documentação, análise de código, revisão crítica e geração de testes.
- **OpenCode:** Atua como "dev junior" para tarefas de engenharia local, pequenos ajustes e automação de código.
- **AgentForge:** O **runtime operacional** e wizard de criação de agentes, rodando preferencialmente sobre modelos locais (Ollama).

## 5. Público-alvo
- **Engenheiros de SRE e DevOps:** Que buscam automação inteligente em ambientes restritos ou locais.
- **Desenvolvedores Python:** Que precisam de um framework para criar agentes previsíveis e versionáveis.
- **Arquitetos de IA:** Que buscam desacoplar a inteligência do agente da infraestrutura de nuvem.

## 6. Escopo Atual (v1)
- **Wizard de Criação:** Fluxo interativo para gerar o ecossistema do agente (`agent.yaml`, `runtime.yaml`, `system_prompt.md`).
- **Memória Multi-turn:** Gestão de histórico com políticas de persistência.
- **Runtime Engine:** Motor de execução que isola a lógica de negócio da inferência do modelo.
- **Tool Registry:** Sistema de despacho de ferramentas com validação de schema e metadados contextuais.

## 7. Não-objetivos
- Não é um framework focado em chat criativo ou conversas genéricas.
- Não busca resolver orquestração multi-agente complexa nesta fase (foco no agente unitário robusto).
- Não é um wrapper para APIs de nuvem; estas são tratadas como secundárias.

## 8. Critérios de Sucesso
- Executar o agente `lab-ops` em modelos de 4B a 9B (Gemma/Qwen) com sucesso em tarefas de diagnóstico de infraestrutura.
- Garantir estabilidade do histórico de conversas após mais de 10 turnos de interação.
- Criar e colocar um agente operacional em execução em menos de 5 minutos via Wizard.
