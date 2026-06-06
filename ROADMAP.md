# Roadmap — AgentForge

Framework de agentes LLM on-prem spec-first e local-first. Evolução guiada pela tese empírica validada ao longo de 4 meses de benchmarks: **20% é o modelo, 80% é o runtime**.

---

## Estado atual: Fase 4 completa

Todas as fases planejadas estão implementadas e cobertas por 291 testes.

---

## Fase 1 — Núcleo ✅

**Objetivo:** Framework spec-first com runtime testável e providers plugáveis.

- `AgentSpec` via Pydantic (identidade, persona, ferramentas, memória, guardrails, eval)
- Wizard interativo para criação de specs
- Geração de artefatos (`system_prompt.md`, `runtime.yaml`, `tools.yaml`, `eval.yaml`, `README.md`)
- `AgentRuntime.from_agent_dir()` — carrega e executa
- `OllamaProvider` e `MockProvider`
- Validação de specs via CLI
- Canal CLI (`agentforge run`)
- Memória multi-turn com políticas `truncate` e `summarize`
- Testes unitários e de integração

---

## Fase 2 — Produto de Teste Viável (PTV) ✅

**Objetivo:** Agente de referência funcional com logging e avaliação.

- Agente `lab-ops` — monitoramento de infra como referência
- Logging JSONL persistente em `agents/<id>/runs/runs.jsonl`
- Comando `agentforge eval` com dataset YAML
- `eval_dataset.yaml` com 8 casos de teste para lab-ops
- Dataset de avaliação estruturado

---

## Fase 3 — Pesquisa: Tool Calling, Robustez e Avaliação ✅

**Objetivo:** Pipeline model-driven de tool calling com mecanismos de robustez.

- **Tool calling model-driven**: modo `respond_or_tool` via protocolo OpenAI/Ollama nativo
- **Loop guard**: detecta `(tool, args)` repetidos no mesmo ciclo, interrompe antes de esgotar o orçamento
- **Reflexão autônoma**: N rounds de auto-crítica configuráveis por spec (`reflection_rounds`)
- **LLM Judge**: scoring multidimensional por critérios, suporta Ollama local e Gemini
- **Guardrails ativos**: verificação de `must_not` com até 2 retries automáticos
- Campos `when_to_use` / `when_not_to_use` no ToolSpec como dicas de decisão para modelos locais

---

## Fase 4 — Canais, UX e Multi-Agente ✅

**Objetivo:** Mesmo agente acessível por qualquer interface sem alterar a spec.

- **HTTP** (`agentforge serve`): FastAPI REST com `/run` e `/health`, compatível com n8n e automações
- **MCP** (`agentforge mcp`): servidor FastMCP expondo 4 ferramentas para Claude Code/Desktop
- **Telegram** (`agentforge telegram`): bot polling assíncrono com typing action e sinalização de guardrails
- `.mcp.json` na raiz — ativa as ferramentas automaticamente no Claude Code
- **Multi-agente híbrido**: `workflow.agents` declara workers; engine injeta `run_agent` no schema; modelo escolhe quando e para quem delegar
- `agents/orchestrator/` — agente orquestrador de referência delegando para lab-ops

---

## Fase 5 — Observabilidade, Streaming e Multi-Agente (planejado)

**Objetivo:** Tornar o runtime pronto para produção e expandir capacidades de orquestração.

### Observabilidade

- [ ] Traces estruturados por run (thought → action → observation → output)
- [ ] Painel de métricas: latência, taxa de tool use, taxa de guardrail trigger
- [ ] Export OpenTelemetry para integração com sistemas externos
- [ ] Dashboard no fox-noc para runs do AgentForge

### Streaming

- [ ] Suporte a `stream: true` no OllamaProvider
- [ ] Streaming de tokens no canal HTTP (Server-Sent Events)
- [ ] Streaming no canal Telegram (edit_message progressivo)

### Guardrails avançados

- [ ] Verificação de `must` (regras de presença, não apenas ausência)
- [ ] Guardrails de tool use: limitar quais ferramentas podem ser chamadas em contextos específicos
- [ ] Orçamento de tokens por run (interrompe se exceder)

### Multi-Agente

- [ ] Orchestrator: agente que delega subtarefas para outros agentes
- [ ] Protocolo de handoff entre agentes via agent-mesh
- [ ] Paralelismo: execução de N agentes em paralelo, combinação de resultados

### Canal Web

- [ ] Interface chat simples (HTML/JS) servida pelo canal HTTP
- [ ] Histórico de conversas por sessão no browser

---

## Decisões de design registradas

| Decisão | Motivação |
|---|---|
| Spec YAML como fonte única de verdade | Versionável, auditável, legível por humanos e modelos |
| Tool calling via protocolo OpenAI/Ollama nativo | Sem abstração proprietária — funciona com qualquer modelo compatível |
| Guardrails pós-geração, não pré-prompt | Mais confiável: verifica o output real, não o comportamento esperado |
| `MockProvider` para testes | Testes determinísticos sem dependência de Ollama no CI |
| `qwen3.5:9b` como modelo padrão | Melhor custo-benefício validado em ABS — 7 GB VRAM, 91% de qualidade |
| `when_to_use` / `when_not_to_use` no ToolSpec | Modelos locais precisam de dicas explícitas de decisão — reduz chamadas erradas |
| Logging JSONL por run | Auditável, streamable, não requer banco de dados |
