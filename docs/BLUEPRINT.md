# AgentForge — Blueprint Técnico v1

> **Nota:** Este documento é o blueprint original do projeto (Fase 1). Para a referência técnica completa e atualizada, incluindo tool calling, guardrails, canais e arquitetura atual, veja [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Visão Geral

O AgentForge funciona como um sistema *spec-driven*. O fluxo de execução original:

```
Wizard → Spec (YAML) → Artefatos de Agente → Engine → Provider (Ollama/Mock) → Memória/Tools
```

A arquitetura garante que a inteligência (o prompt e as regras) esteja desacoplada da execução física, permitindo trocar o modelo ou o provider sem alterar a lógica do agente.

## 2. Componentes Principais

### Core e Specs

- **AgentSpec (`agent_models.py`)**: Define o contrato rigoroso do agente via Pydantic.
- **Validation**: Garante que o `agent.yaml` e as `tools.yaml` sigam o esquema oficial em `/specs`.

### Runtime Engine

- **Engine**: Orquestra o ciclo de vida da requisição. Carrega as mensagens, aplica as políticas de memória, despacha chamadas para o LLM e executa as ferramentas selecionadas.
- **Provider Registry**: Permite o uso de `Ollama` como padrão e `Mock` para CI e testes determinísticos.

### Tools e Registry

- **Registry**: Gerencia funções Python registradas que o agente pode chamar.
- **Tool Metadata**: Além do schema JSON, o framework utiliza campos `when_to_use` e `when_not_to_use`. Crítico para modelos locais — funcionam como dicas de decisão que reduzem chamadas errôneas.

## 3. Memória e Políticas de Histórico

- **`max_turns`**: Define o horizonte máximo de memória do agente.
- **`policy: truncate`**: Remove as mensagens mais antigas de forma determinística.
- **`policy: summarize`**: Condensa o histórico em formato bullet-point estável.

## 4. O Wizard de Agentes

O `agentforge wizard` automatiza a engenharia de agentes ao coletar:
- Identidade, Persona e Propósito
- Configurações de memória e canal
- Seleção de ferramentas e seus schemas
- Guardrails (`must` / `must_not`)

**Saída**: Um diretório autocontido com o `system_prompt.md` estruturado e arquivos de configuração YAML prontos para o `AgentRuntime`.

## 5. Agente de Referência: lab-ops

O `lab-ops` é o agente de referência do framework. Veja [`../agents/lab-ops/README.md`](../agents/lab-ops/README.md) para documentação completa.

## 6. Estrutura de Testes e Avaliação

- **Testes Unitários**: Validação de models, schemas e lógica do Wizard.
- **Runtime Tests**: Testes usando `MockProvider` para garantir que o fluxo de decisão e memória do Engine está correto.
- **Agent Evaluation**: Uso de dataset YAML para verificar consistência da saída do agente.

## 7. Evolução desde o Blueprint v1

Capacidades adicionadas após este blueprint:

| Fase | O que foi adicionado |
|---|---|
| Fase 2 | Logging JSONL, `agentforge eval`, agente lab-ops como PTV |
| Fase 3 | Tool calling model-driven, loop guard, reflexão autônoma, LLM judge, guardrails ativos |
| Fase 4 | Canal HTTP (FastAPI), Canal MCP (FastMCP), Canal Telegram, `.mcp.json` |

Para detalhes técnicos de cada um, veja [`ARCHITECTURE.md`](ARCHITECTURE.md).
