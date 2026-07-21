# Spec: Migração do funil de certificação (ABS/LOP/FORGE/REAL) pro motor real do AgentForge

## Objetivo

Hoje o funil de certificação de modelos locais tem 4 fases, e só uma (AgentForge F3/P3) roda pelo motor de verdade (`AgentRuntime.run()` em `src/agentforge/runtime/engine.py`), que carrega loop_guard, must_compliance, guardrails e as demais 16 correções documentadas em `feedback_agentforge_engine_bugs.md`. As outras três fases (ABS, LOP, FORGE, REAL) usam runners próprios — cada um reimplementando seu próprio mini-loop de tool call, sem nenhuma dessas mitigações.

Isso gera dois problemas:
1. **Comparação injusta entre modelos** — um modelo pode "perder" pontos por instabilidade que o harness de produção já resolve (loop de tool call, por exemplo), e outro pode "ganhar" por sorte de não ter caído nesse padrão específico no teste cru.
2. **O funil não prevê comportamento real de produção** — só a fase final (F3/P3) reflete o que realmente vai rodar no AgentForge em uso normal.

**Meta:** todo cenário do funil (ABS: 23, LOP: 4, FORGE: 5, REAL: 4 — total ~36) passa a rodar via `AgentRuntime.run()`, reaproveitando os prompts/task-files/critérios de auto_check já existentes, sem reescrever a lógica de avaliação de cada cenário do zero.

**Quem usa isso:** Conrado, na hora de decidir campeão/candidatos de modelo local pro fox-server. Motivador imediato: comparação Agents-A1 vs qwen3.6-35B-A3B em 2026-07-20 já mostrou casos onde o resultado cru distorcia o quadro (ver `project_funil_harness_redesign_pendencia.md`).

## Repos envolvidos

| Repo | Papel hoje | O que muda |
|---|---|---|
| `~/repos/estudo/agents-framework/` | Motor (`engine.py`), registry de tools, runner atual de F3/P3 (`scripts/run_benchmark_eval.py`) | Vira o **hub único** — todos os cenários passam a ter agent-spec aqui |
| `~/repos/estudo/agent-benchmark-suite/` (ABS) | Runner próprio (`run.py`), 23 cenários em Python (`abs/scenarios/*.py`) | Cenários viram fonte de prompt/auto_check reaproveitada; runner próprio aposentado |
| `~/repos/estudo/llms-on-prem/` (LOP) | 8 scripts standalone (`scripts/run-s{1,2,2b,3,4,4b-v2,4-thinking}-benchmark.py`) | Idem — scripts standalone aposentados |
| `~/repos/estudo/forge/` | `forge_runner.py` (1045 linhas, loop de tool próprio) | Loop próprio aposentado; scenarios/*.json e TASK.md continuam sendo a fonte |
| `~/repos/estudo/real/` | `real_runner.py` (726 linhas, loop de tool próprio + tools de browser) | Idem; tools de browser precisam ser portadas pro AgentForge (ver Gaps) |

## Como rodar hoje vs como vai rodar

**Hoje** (exemplo F3, já migrado — é o modelo a seguir):
```bash
cd ~/repos/estudo/agents-framework
export AGENTFORGE_PROVIDER=llamacpp
export LLAMACPP_HOST=http://localhost:8083
python3 scripts/run_benchmark_eval.py --model agents-a1 --scenarios F3 P3 --provider llamacpp
```
Isso lê `agents/forge-f3/agent.yaml` (spec: tools, guardrails `must`, `model_policy`, `workflow.max_tool_cycles`), constrói um `AgentSpec` + `RuntimeConfig`, e chama `AgentRuntime.run()`.

**Depois** (meta): o mesmo comando, com `--scenarios` aceitando qualquer cenário de qualquer fase:
```bash
python3 scripts/run_benchmark_eval.py --model agents-a1 --scenarios Q1 T4 S2 F1 P2 F3 P3 --provider llamacpp --runs 3
```

## Gaps identificados (bloqueiam início até resolver)

### 1. Tools de browser do REAL não existem no AgentForge

`real_runner.py` usa `browser_navigate`, `browser_execute_js`, `browser_screenshot`, `browser_get_element`, `browser_fill_and_submit`. Nenhuma está em `src/agentforge/tools/`.

**Caminho de porte:** o AgentForge já tem mecanismo pronto pra isso — Tool Registry dinâmico (`docs/TOOL-REGISTRY.pt-BR.md`). Portar as 5 funções de `real_runner.py` como arquivos em `tool_registry/`, registrar em `registry.yaml` no mesmo formato que `search_memory` já usa. Não precisa mexer em `registry.py` core.

### 2. `http_post` e `append_file` do FORGE também faltam

Portes simples, mesmo mecanismo do item 1.

### 3. ABS não tem estrutura de "task file" — cenários são gerados em Python puro

FORGE/REAL já usam o padrão "JSON de cenário + TASK.md" que `run_benchmark_eval.py` sabe ler. ABS (`abs/scenarios/q_series.py` etc.) gera prompt+auto_check em código Python direto, sem esse formato.

**Decidido:** extrair os 23 cenários pra JSON+task-file (mesmo padrão do FORGE/REAL) — **sem alterar** `abs/scenarios/*.py` original. A extração gera uma cópia derivada; o código-fonte do ABS continua intocado e utilizável pelo `run.py` antigo se algum dia precisar.

### 4. LOP: mesma extração, com restrição extra

LOP é estudo científico — os scripts `run-s{1..4}-benchmark.py` **não podem ser modificados em si**. Mesma abordagem do item 3 (extrair cenário pra JSON+task-file como cópia derivada), mas aqui a regra de não tocar no original é ainda mais estrita, não é só preferência de implementação.

## Project Structure (proposta)

```
agents-framework/
├── agents/
│   ├── forge-f1/ ... forge-f5/        ← novos, seguindo padrão forge-f3/
│   ├── real-p1/ real-p2/ real-p4/     ← novos, seguindo padrão real-p3/
│   ├── abs-q1/ ... abs-m2-h/          ← novos, 23 specs (ou 1 spec parametrizado — decidir no Plan)
│   └── lop-s1/ ... lop-s4/            ← novos
├── tool_registry/
│   ├── browser_navigate.py            ← portado de real_runner.py
│   ├── browser_execute_js.py
│   ├── browser_screenshot.py
│   ├── browser_get_element.py
│   ├── browser_fill_and_submit.py
│   ├── http_post.py                   ← portado de forge_runner.py
│   └── append_file.py
└── scripts/
    └── run_benchmark_eval.py          ← estendido pra aceitar qualquer cenário das 4 fases
```

## Code Style

Seguir o padrão já estabelecido em `agents/forge-f3/*.yaml` — não inventar formato novo. `agent.yaml` com `tools:`, `guardrails.must:`, `model_policy:`, `workflow.max_tool_cycles/reflection_rounds`. Tools novas seguem o padrão de `tool_registry/search_memory.py` (função pública + JSON schema).

## Testing Strategy

- Cada cenário migrado: rodar 1x contra um modelo já testado no funil antigo (ex: qwen3.6-35b-a3b-nothink) e comparar auto_pct — não precisa bater 100%, mas divergência grande sinaliza erro de porte, não mudança de comportamento real.
- Antes de aposentar um runner antigo, os dois (antigo + novo) precisam rodar em paralelo pelo menos 1x pra cada cenário daquela fase, com resultado registrado lado a lado.
- Não apagar `forge_runner.py`/`real_runner.py`/scripts do LOP/`run.py` do ABS — só parar de usar. Histórico de git resolve se precisar recuperar.

## Boundaries

- **Sempre:** manter os cenários (prompts, TASK.md, critérios de auto_check) como fonte de verdade — não reescrever critério de avaliação durante a migração, só o mecanismo de execução.
- **Sempre:** extração de cenário (ABS/LOP) gera arquivo novo/derivado — nunca edita o original no processo.
- **Nunca:** modificar `~/repos/estudo/llms-on-prem/` (scripts, resultados, qualquer arquivo) — é estudo científico, alteração ali não é decisão de engenharia, é decisão de pesquisa que não é desse projeto.
- **Nunca:** apagar os runners antigos (`forge_runner.py`, `real_runner.py`, scripts do ABS/LOP) ou os resultados já coletados (`results/`, `benchmark_results/`) antes de confirmar que a versão nova está validada.

## Ordem de implementação

Decidida: **REAL → FORGE → LOP → ABS**, do mais parecido com o AgentForge de hoje pro mais distante.

1. **REAL** — P3 já roda no motor real; P1/P2/P4 usam tools de browser que só precisam ser portadas (gap 1), estrutura de agent-spec já é a mesma coisa. É o salto mais curto.
2. **FORGE** — F3 já migrado; F1/F2/F4/F5 seguem o mesmo padrão de agent-spec + task-file que F3 já usa, só falta portar `http_post`/`append_file` (gap 2).
3. **LOP** — precisa da extração não-destrutiva (gap 4) antes de começar; formato ainda não mapeado a fundo, maior incógnita depois do ABS.
4. **ABS** — maior distância do padrão atual (23 cenários em Python puro, sem task-file); fica por último de propósito.

## Success Criteria

- [ ] Os 5 gaps de tool (browser×5, http_post, append_file) portados e registrados
- [ ] FORGE F1-F5 rodando 100% via `AgentRuntime.run()`, runner antigo aposentado
- [ ] REAL P1,P2,P4 rodando 100% via `AgentRuntime.run()`, runner antigo aposentado
- [ ] Decisão tomada e implementada pro formato ABS/LOP (item 3/4)
- [ ] ABS (23 cenários) e LOP (4 fases) rodando via `AgentRuntime.run()`
- [ ] Um modelo já certificado antes (ex: campeão atual) reavaliado no funil novo, resultado comparado lado a lado com o funil antigo — documentado

## Plan — Fase 1: REAL (primeira da fila)

Investigação confirmou que REAL é o salto mais curto possível: `P1.json`, `P2.json`, `P4.json` já têm **exatamente a mesma estrutura** que `P3.json` (campos `id, name, description, difficulty, wall_timeout_s, stuck_window, prompt, auto_checks, judge_rubric`), e **todos os tipos de `auto_check`** usados por P1/P2/P4 (`no_error`, `file_contains`, `json_has_keys`, `tool_called`, `response_contains`, `json_valid`, `file_exists`, `skill_has_frontmatter`, `skill_has_sections`) **já estão implementados** em `run_benchmark_eval.py`. Nada a portar do lado de avaliação — só do lado de execução (tools de browser).

Necessidade de tool por cenário:
| Cenário | Tema | Precisa de browser? |
|---|---|---|
| P1 | Scraping de notícias (Hacker News) | Sim — `browser_navigate` |
| P2 | SPA com JS dinâmico | Sim — `browser_navigate`, `browser_execute_js`, `browser_get_element` |
| P4 | Gerador de skill Claude | Não — só `write_file`, `read_file`, `run_bash` (igual P3) |

### Tasks

- [ ] **Portar as tools de browser pro Tool Registry**
  - Acceptance: `browser_navigate`, `browser_execute_js`, `browser_get_element` viram arquivos em `tool_registry/`, registrados em `registry.yaml`, com teste pytest cobrindo cada uma (`browser_screenshot`/`browser_fill_and_submit` não são usadas por P1/P2/P4 — portar só se algum cenário futuro precisar)
  - Verify: `pytest tool_registry/test_browser_*.py` passa; tool aparece em `execute_tool` sem reiniciar nada além do processo do runner
  - Files: `tool_registry/browser_navigate.py`, `browser_execute_js.py`, `browser_get_element.py`, `registry.yaml` + 3 arquivos de teste

- [ ] **Criar agent.yaml pra real-p1, real-p2, real-p4**
  - Acceptance: 3 diretórios novos em `agents/`, seguindo o padrão de `agents/real-p3/` (tools, guardrails, model_policy, workflow) — p1/p2 listam as tools de browser, p4 replica p3
  - Verify: `python3 scripts/run_benchmark_eval.py --scenarios P1 --model <modelo-conhecido>` roda sem erro de spec inválido
  - Files: `agents/real-p1/agent.yaml`, `agents/real-p2/agent.yaml`, `agents/real-p4/agent.yaml`

- [ ] **Estender `SCENARIO_MAP`/`AGENT_MAP` em `run_benchmark_eval.py`**
  - Acceptance: P1, P2, P4 aceitos por `--scenarios`, apontando pros JSONs existentes em `real/scenarios/` (sem cópia — usar direto, já que não há restrição de "não tocar" pro REAL como há pro LOP)
  - Verify: os 4 cenários do REAL (P1,P2,P3,P4) rodam numa chamada só
  - Files: `scripts/run_benchmark_eval.py`

- [ ] **Validar contra resultado do `real_runner.py`**
  - Acceptance: rodar P1/P2/P4 via `run_benchmark_eval.py` com qwen3.6-35b-a3b-nothink (mesmo modelo já testado no runner antigo), comparar `auto_pct` — divergência grande sinaliza erro de porte
  - Verify: resultado lado a lado documentado (pode ir de volta pra `project_funil_harness_redesign_pendencia.md` como registro)
  - Files: nenhum (só execução + comparação)

- [ ] **Aposentar `real_runner.py`**
  - Acceptance: script continua existindo no repo (não apagar), mas para de ser chamado por qualquer script de funil (`run_agents_a1_full_funil.sh` e equivalentes passam a usar só `run_benchmark_eval.py` pra REAL)
  - Verify: grep por `real_runner.py` em scripts de funil não retorna chamada ativa, só histórico
  - Files: scripts de funil (`run_*_full_funil.sh`)

FORGE, LOP e ABS ficam pra sessões seguintes, cada um com seu próprio Plan quando chegar a vez — não vou detalhar os três de antemão pra não gerar plano obsoleto antes de aprender o que a fase REAL ensinar.

## Open Questions

1. **ABS: 1 spec parametrizado (single-turn) — detalhar no Plan.** Direção decidida (single-turn, sem workdir pesado tipo FORGE/REAL), mas o desenho exato (1 `agent.yaml` genérico + 23 pares prompt/auto_check parametrizados, vs. outra estrutura) ainda precisa de conversa — deixado pro início da fase ABS (última da fila), não bloqueia REAL/FORGE/LOP.
