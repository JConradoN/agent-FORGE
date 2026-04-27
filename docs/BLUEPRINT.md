# AgentForge — Blueprint Técnico v1

## 1. Visão Geral
O AgentForge funciona como um sistema *spec-driven*. O fluxo de execução é:
`Wizard -> Spec (YAML) -> Artefatos de Agente -> Engine -> Provider (Ollama/Mock) -> Memória/Tools`.

A arquitetura garante que a inteligência (o prompt e as regras) esteja desacoplada da execução física, permitindo trocar o modelo ou o provider sem alterar a lógica do agente.

## 2. Componentes Principais

### Core e Specs
- **AgentSpec (`agent_models.py`)**: Define o contrato rigoroso do agente via Pydantic.
- **Validation**: Garante que o `agent.yaml` e as `tools.yaml` sigam o esquema oficial em `/specs`.

### Runtime Engine
- **Engine**: Orquestra o ciclo de vida da requisição. Ele carrega as mensagens, aplica as políticas de memória, despacha chamadas para o LLM e executa as ferramentas selecionadas.
- **Provider Registry**: Permite o uso de `Ollama` como padrão e `Mock` para CI e testes determinísticos.

### Tools e Registry
- **Registry**: Gerencia funções Python registradas que o agente pode chamar.
- **Tool Metadata**: Além do schema JSON, o framework utiliza campos como `when_to_use` e `when_not_to_use`. Isso é crítico para modelos locais, funcionando como "dicas de decisão" que reduzem chamadas errôneas de ferramentas.

## 3. Memória e Políticas de Histórico
A gestão de memória é fundamental para evitar a degradação do modelo local:
- **`max_turns`**: Define o horizonte máximo de memória do agente.
- **`policy: truncate`**: Remove as mensagens mais antigas de forma determinística.
- **`policy: summarize`**: 
    - **Padrão**: Implementação determinística que condensa o histórico em um formato bullet-point estável.
    - **Hook Opcional**: Pode-se plugar um LLM para gerar resumos mais semânticos, mas o sistema é funcional e seguro para testes mesmo sem este hook.

## 4. O Wizard de Agentes
O `agentforge wizard` automatiza a engenharia de agentes ao coletar:
- Identidade, Persona e Propósito.
- Configurações de memória e canal.
- Seleção de ferramentas e seus schemas.
- Guardrails (`must` / `must_not`).
**Saída**: Um diretório autocontido com o `system_prompt.md` estruturado e arquivos de configuração YAML prontos para o `AgentRuntime`.

## 5. Agente de Referência: lab-ops
O `lab-ops` é o agente de referência para demonstração de capacidades:
- **Foco Atual (Monitorar + Diagnosticar)**: Utiliza tools como `collect_system_health` e `read_log_tail` para analisar o estado do servidor e diagnosticar falhas.
- **Visão de Futuro (Agir)**: O design prevê a inclusão de ferramentas de ação controlada (ex: limpar caches, ajustar logs ou rodar scripts de correção) sob guardrails rigorosos de segurança e confirmação manual.

## 6. Estrutura de Testes e Avaliação
- **Testes Unitários**: Validação de models, schemas e lógica do Wizard.
- **Runtime Tests**: Testes de ponta a ponta usando `MockProvider` para garantir que o fluxo de decisão e memória do Engine está correto.
- **Agent Evaluation**: Uso de perguntas de controle para verificar a consistência da saída do agente após mudanças na especificação.

## 7. Limitações e Evolução Técnica
- **Traces e Observabilidade**: Implementação pendente de logs de execução que separem claramente Pensamento (*Thought*) de Ação (*Action*).
- **Async Runtime**: O motor atual é síncrono, adequado para CLI, mas requer evolução para suportar interfaces assíncronas (Web/Telegram).
- **Tool Execution Guardrails**: Evoluir o sistema de permissões para permitir ações de escrita no sistema de forma segura.
