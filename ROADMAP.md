# Roadmap — AgentForge Lab

Este roadmap descreve a evolução planejada do framework de agentes LLM on‑prem, com foco em previsibilidade, avaliação e experimentação em ambiente local (Ollama).

O objetivo é chegar rapidamente a um **Produto de Teste Viável** e, a partir dele, iterar em features de pesquisa (tools, guardrails, avaliação).

---

## Visão geral por fases

- Fase 1 — Núcleo do framework (agora)
- Fase 2 — Produto de Teste Viável (PTV)
- Fase 3 — Pesquisa: tools, guardrails, avaliação
- Fase 4 — Canais e UX (Telegram/Web)
- Fase 5 — Otimização, observabilidade e refino

---

## Fase 1 — Núcleo do framework (estado atual)

### Objetivo

Ter um framework **spec‑first** que:

- define agentes por YAML/AgentSpec;
- gera artefatos derivados;
- carrega e executa um runtime local;
- suporta providers pluggáveis;
- é amplamente coberto por testes.

### Status

✅ Implementado:

- **Specs**
  - `framework.spec.yaml` e `orchestrator.spec.yaml`
  - `AgentSpec` com:
    - `agent`, `persona`, `channel`, `tools`, `memory`, `output`,
      `guardrails`, `eval`, `deployment`, `model_policy`, `workflow`

- **Wizard**
  - `agentforge wizard`
    - coleta informações básicas do agente
    - gera `agents/<id>/agent.yaml`

- **Validação**
  - `agentforge validate` — framework/orquestrador
  - `agentforge validate-agent --path ...` — AgentSpec

- **Geração de artefatos**
  - `agentforge generate --path agents/<id>/agent.yaml` gera:
    - `system_prompt.md`
    - `runtime.yaml`
    - `eval.yaml`
    - `tools.yaml`
    - `README.md`

- **Runtime**
  - `AgentRuntime.from_agent_dir(...)`:
    - carrega `agent.yaml`, `runtime.yaml`, `tools.yaml`
  - `AgentRuntime.run(input_text, metadata=None)`:
    - lê `system_prompt.md` se existir
    - resolve provider via registry
    - chama provider
    - retorna dict estruturado com:
      - `agent_id`, `provider`, `input`, `output`,
        `metadata`, `provider_response`

- **Providers**
  - `mock` — determinístico, para testes/CI
  - `ollama` — chama `/api/generate` local (`stream: false`),
    com timeout explícito

- **CLI**
  - `agentforge info`
  - `agentforge validate`
  - `agentforge wizard`
  - `agentforge validate-agent`
  - `agentforge generate`
  - `agentforge run`

- **Qualidade**
  - ~120 testes cobrindo:
    - modelos
    - wizard
    - geração
    - runtime
    - providers
    - CLI

### Próximos passos de Fase 1 (opcionais, pequenos)

- Escrever documentação interna:
  - `docs/architecture.md` — visão de alto nível (wizard → generate → runtime → providers)
  - `docs/runtime.md` — detalhes de AgentRuntime, RuntimeConfig e providers
- Revisar nomes/campos de spec onde ainda estiver “feio” ou ambíguo

---

## Fase 2 — Produto de Teste Viável (PTV)

### Objetivo

Ter pelo menos **um agente “oficial”** rodando em cima do framework, com:

- criação via wizard;
- execução com provider real (Ollama);
- logging mínimo;
- avaliação simples;
- repetibilidade de testes.

Esse PTV será o **“campo de provas”** para os experimentos de tools, guardrails e avaliação.

### Critérios de PTV

Um agente é considerado PTV quando:

- [ ] Pode ser criado com `agentforge wizard` sem edição de YAML manual
- [ ] `agentforge generate` gera system prompt, runtime, eval e readme consistentes
- [ ] `agentforge run` roda o agente com provider `ollama` e responde de forma útil
- [ ] Existe pelo menos um `eval.yaml` conectado a esse agente
- [ ] Existe pelo menos um pequeno dataset de testes (5–10 entradas) para esse agente
- [ ] Cada execução gera um log (mesmo simples) com:
  - input
  - output
  - provider
  - modelo
  - timestamp
- [ ] É possível repetir o mesmo teste amanhã com o mesmo resultado, usando as mesmas specs

### Escopo da Fase 2

1. **Logging estruturado simples**

   - Introduzir um logger de runtime que grave um arquivo por agente, por exemplo:
     - `agents/<id>/runs/runs.jsonl`
   - Para cada `run()`:
     - escrever uma linha JSON com:
       - `agent_id`
       - `provider`
       - `model`
       - `input`
       - `output`
       - `timestamp`
       - `latency_ms`
   - Foco em observabilidade mínima para o laboratório.

2. **Executor de avaliação simples**

   - Novo comando CLI:
     - `agentforge eval --agent-dir agents/<id> --dataset path/to/dataset.yaml`
   - Dataset mínimo:
     - lista de casos com:
       - `input`
       - `notes` (opcional)
   - Execução:
     - para cada caso:
       - chamar `AgentRuntime.run(input)`
       - registrar resultado em:
         - `agents/<id>/eval_runs/<timestamp>.jsonl` (por exemplo)
   - Sem autometria sofisticada ainda:
     - análise pode ser manual a partir dos logs.

3. **Agente de referência (v0)**

   Um agente “oficial” para servir como PTV:

   - Nome: `Claudio Assistente CLI`
   - Canal:
     - CLI (por enquanto)
   - Provider:
     - `ollama`
   - Model:
     - `qwen3.5:9b`
   - Objetivo:
     - responder perguntas gerais com foco técnico (laboratório)
   - Artefatos:
     - `agent.yaml` (wizard + ajustes)
     - `system_prompt.md` afinado à mão
     - `eval.yaml` + dataset de 5–10 perguntas
     - README dedicado

---

## Fase 3 — Pesquisa: tools, guardrails, avaliação

### Objetivo

Explorar de forma sistemática:

- tool use;
- guardrails;
- avaliação de qualidade e consistência.

Baseado nos achados do laboratório:

- semântica, formato e tool use são dimensões ortogonais;
- falhas de decisão de ação são mais corrigíveis por prompt do que falhas de formato;
- instruções explícitas de tool (nome + args) aumentam muito a confiabilidade.

### Escopo inicial

1. **Camada de tools no runtime (sem LLM decidindo ainda)**

   - Ler `tools.yaml` e materializar uma estrutura `ToolRuntimeSpec`.
   - Definir contrato para execução de tool:
     - interface Python
     - input/output tipados
   - Primeiro passo:
     - execução de tools acionadas explicitamente (não pelo modelo), só para provar a infraestrutura.

2. **Workflow e guardrails mínimos**

   - Implementar pelo menos um workflow explícito, por exemplo:
     - `respond_or_tool`
   - Definir políticas como:
     - quando input contiver `file://` → chamar tool de leitura antes de responder
   - Guardrails:
     - impedir inferência com base apenas em nome de arquivo/path
     - exigir evidência de execução de tool quando marcada como “obrigatória”

3. **Avaliação orientada a experimento**

   - Estruturar melhor `eval.yaml`:
     - métricas desejadas
     - datasets associados
   - Criar scripts/notebooks para:
     - comparar runs com providers/modelos diferentes
     - medir:
       - taxa de uso correto de tool
       - taxa de formato válido
       - variância entre runs (consistência)

---

## Fase 4 — Canais e UX (Telegram/Web)

### Objetivo

Levar o agente para canais reais, mantendo o runtime core intacto.

### Escopo

1. **Canal CLI polido**
   - Melhorar experiência de linha de comando para uso diário do laboratório.

2. **Canal Telegram (Claudio Assistente)**
   - Adapter Telegram:
     - recebe mensagem
     - chama AgentRuntime
     - envia resposta
   - Focar em:
     - robustez
     - logs
     - limites de comprimento

3. **UI Web mínima (opcional após Telegram)**
   - Interface simples para:
     - selecionar agente
     - enviar input
     - ver resposta + metadata básica

---

## Fase 5 — Otimização, observabilidade e refino

### Objetivo

Refinar o framework para uso contínuo no laboratório:

- otimizar rota de modelos;
- melhorar observabilidade;
- refinar DX.

### Possíveis itens

- Roteamento esperto (LiteLLM opcional) quando fizer sentido:
  - semântica mais pesada → modelo X
  - formato estrito → modelo Y
- Observabilidade:
  - métricas de latência, erro, uso de provider/modelo
- Refino de prompts e templates:
  - system prompts mais consistentes
  - templates de agente por tipo de tarefa

---

## Prioridades imediatas (próximos passos práticos)

1. Documentação
   - [ ] Criar `docs/architecture.md` e `docs/runtime.md`
   - [ ] Atualizar `README.md` com o fluxo wizard → generate → run

2. Produto de Teste Viável
   - [ ] Implementar logging JSONL simples de run() por agente
   - [ ] Implementar `agentforge eval` com dataset mínimo
   - [ ] Criar e estabilizar o agente `Claudio Assistente CLI` como PTV

Depois que esses itens estiverem prontos, o framework estará pronto para ciclos sistemáticos de experimento com tools, guardrails e avaliação, que são o foco central do laboratório.
