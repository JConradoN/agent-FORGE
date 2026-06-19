# AGY_AGENTFORGE_V3 — Dataset Focado nos Gaps do claudio-9b-v2

## Objetivo

Corrigir os gaps identificados no benchmark completo FORGE/REAL (2026-06-19) do claudio-9b-v2.
O modelo base qwen3.5:9b marcou 85% e o fine-tuned v2 marcou apenas 67% — catastrophic forgetting.

**Problemas identificados:**
1. F1 (27% vs 81%): modelo tenta write_file com HTML inteiro (>15 KB) → JSON malformado. Precisa dividir em write_file + append_file
2. F5 (24% vs 71%): após ler código com run_bash/read_file, modelo não escreve relatórios estruturados
3. P3 (67% vs 93%): testes pytest falham por falta de isolamento SQLite (shared state entre tests)
4. F3 (94% vs 100%): headings exatos (COTAÇÕES, RECOMENDAÇÃO) e frase ANÁLISE CONCLUÍDA
5. Catastrophic forgetting geral: dataset V2 era 100% agentic → modelo perdeu raciocínio livre

**Estratégia V3:**
- ~300 exemplos: 140 gaps de benchmark + 160 generalização
- O modelo é generalista: opera AgentForge no dia a dia com tools, skills e agents criados dinamicamente
- Capacidade central a treinar: ler qualquer schema de tool → entender o que faz → usar corretamente
- O engine passa o schema completo (name, description, parameters) a cada chamada — modelo não memoriza nomes
- Usar qwen3.5:27b como gerador (melhor qualidade para código e raciocínio complexo)

**Arquivo de saída:** `/home/conrado/repos/estudo/agents-framework/finetune/dataset/synth_v3_overnight.jsonl`
**IDs:** `v3-c001` em diante
**Formato:** JSONL, uma linha por exemplo, sem quebra de linha dentro do JSON

---

## Como o engine funciona — referência (igual V2)

```
1. user_input + must_rules → injetados no user message
2. Loop: assistant(tool_calls) → tool(result) → ...
3. Sem tool quando há tools → engine injeta "use the available tools"
4. Após max_cycles → completion_hint com frase obrigatória
5. must_not guardrails: engine injeta "Your previous response violated..."
6. must_compliance: engine injeta "mandatory rules were not met..."
```

**Tools disponíveis nos cenários FORGE:**
- `write_file(path, content)` → cria/sobrescreve arquivo
- `append_file(path, content)` → adiciona ao final de arquivo existente
- `run_bash(command)` → executa comando bash
- `read_file(path)` → lê conteúdo de arquivo
- `http_get(url)` → faz GET e retorna texto
- `send_claudio(message)` → envia notificação via Telegram

**Tools disponíveis nos cenários REAL:**
- `browser_navigate(url, wait_selector)` → abre URL no Playwright
- `execute_js(script)` → executa JS na página aberta
- `write_file(path, content)` → salva arquivo
- `run_bash(command)` → executa comando bash

---

## Formato de cada exemplo

```json
{
  "id": "v3-c001",
  "source": "synthetic_agy_v3",
  "category": "agentforge_v3",
  "subcategory": "<uma das categorias abaixo>",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "...", "arguments": {...}}}]},
    {"role": "tool", "content": "...", "name": "..."},
    {"role": "assistant", "content": "...resposta final..."}
  ]
}
```

**Regras de formato — CRÍTICO:**
- `tool_calls[].function.arguments` é **dict**, nunca string JSON
- role `tool` sempre tem campo `"name"` com o nome da ferramenta
- assistant que invoca tools tem `content: ""` (ou thinking muito breve)
- Última mensagem é sempre `{"role": "assistant", "content": "..."}` com resposta final

---

## CATEGORIA 1 — write_large_file (40 exemplos)

**Problema que resolve:** F1 (27% vs 81%). O modelo tentava escrever HTML/CSS/JS inteiro em
um único write_file, causando JSON malformado (HTTP 500). Precisa aprender a dividir em partes.

**Padrão obrigatório:**
```
user: "Crie um site/app com [requisito complexo]"
assistant: write_file(path="index.html", content="<estrutura HTML base sem CSS/JS, ~2KB>")
tool: {"success": true, "path": "index.html", "bytes": ...}
assistant: append_file(path="index.html", content="<bloco de CSS em style tag, ~3KB>")
tool: {"success": true, "path": "index.html", "bytes": ...}
assistant: append_file(path="index.html", content="<bloco de JS em script tag, ~2KB>")
tool: {"success": true, "path": "index.html", "bytes": ...}
assistant: run_bash(command="python3 -m http.server 8200 &")
tool: "Serving HTTP on 0.0.0.0 port 8200..."
assistant: "PÁGINA PUBLICADA em http://localhost:8200"
```

**Subcategorias (40 exemplos total):**
- `write_large_file_site` (20 ex): sites HTML completos (imobiliária, portfólio, landing page, dashboard)
  - DEVE usar write_file para estrutura + append_file para CSS + append_file para JS
  - Termina com run_bash para servidor + "PÁGINA PUBLICADA"
  - Conteúdo realista: pelo menos 8KB total dividido em 3+ chamadas

- `write_large_file_report` (20 ex): relatórios/documentos longos
  - DEVE usar write_file para cabeçalho + múltiplos append_file para seções
  - Nunca uma chamada write_file/append_file com mais de 4KB de conteúdo
  - Conteúdos: relatórios técnicos, análises, documentação, planos

**Exemplo canônico write_large_file_site:**
```json
{
  "id": "v3-c001",
  "source": "synthetic_agy_v3",
  "category": "agentforge_v3",
  "subcategory": "write_large_file_site",
  "messages": [
    {"role": "system", "content": "Você é um agente de desenvolvimento web rodando em servidor Linux. Tools: write_file, append_file, run_bash, read_file."},
    {"role": "user", "content": "Crie um site de portfólio para desenvolvedor com seção hero, skills e projetos. Use cores escuras (#0D1117 fundo, #58A6FF accent). Sirva na porta 8200. Quando publicar, confirme com 'PÁGINA PUBLICADA'."},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "index.html", "content": "<!DOCTYPE html>\n<html lang='pt-BR'>\n<head>\n<meta charset='UTF-8'>\n<meta name='viewport' content='width=device-width, initial-scale=1.0'>\n<title>Dev Portfolio</title>\n</head>\n<body>\n<header><nav><a href='#hero'>Início</a> <a href='#skills'>Skills</a> <a href='#projects'>Projetos</a></nav></header>\n<section id='hero'><h1>João Silva</h1><p>Desenvolvedor Full Stack & IA</p><a href='#projects' class='cta'>Ver Projetos</a></section>\n<section id='skills'><h2>Skills</h2><ul id='skills-list'></ul></section>\n<section id='projects'><h2>Projetos</h2><div id='projects-grid'></div></section>\n<footer><p>© 2026 João Silva</p></footer>\n</body>\n</html>"}}}]},
    {"role": "tool", "content": "{\"success\": true, \"path\": \"index.html\", \"bytes\": 612}", "name": "write_file"},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "append_file", "arguments": {"path": "index.html", "content": "<style>\n:root { --bg: #0D1117; --accent: #58A6FF; --text: #E6EDF3; --surface: #161B22; }\n* { margin:0; padding:0; box-sizing:border-box; }\nbody { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; }\nnav { display:flex; gap:2rem; padding:1rem 2rem; background: var(--surface); position:sticky; top:0; }\nnav a { color: var(--accent); text-decoration:none; }\n#hero { min-height:80vh; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding:2rem; }\n#hero h1 { font-size:3rem; margin-bottom:1rem; }\n.cta { background: var(--accent); color: #000; padding:.75rem 2rem; border-radius:6px; text-decoration:none; margin-top:1.5rem; font-weight:600; }\n#skills, #projects { padding:4rem 2rem; max-width:1000px; margin:0 auto; }\nh2 { font-size:2rem; margin-bottom:2rem; color: var(--accent); }\n#skills-list { display:flex; flex-wrap:wrap; gap:1rem; list-style:none; }\n#skills-list li { background: var(--surface); padding:.5rem 1.25rem; border-radius:20px; border:1px solid var(--accent); }\n#projects-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:1.5rem; }\n.card { background: var(--surface); border-radius:8px; padding:1.5rem; border:1px solid #30363d; }\n.card h3 { color: var(--accent); margin-bottom:.5rem; }\nfooter { text-align:center; padding:2rem; color:#8b949e; }\n</style>"}}}]},
    {"role": "tool", "content": "{\"success\": true, \"path\": \"index.html\", \"bytes\": 1234}", "name": "append_file"},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "append_file", "arguments": {"path": "index.html", "content": "<script>\nconst skills = ['Python','JavaScript','Go','Docker','LLMs','FastAPI','React','PostgreSQL'];\nconst projects = [\n  {title:'AgentForge',desc:'Framework de agentes LLM com benchmarks e fine-tuning'},\n  {title:'Fox NOC',desc:'Painel de monitoramento em tempo real para homelab'},\n  {title:'Local LLM Bench',desc:'Suite de benchmark para modelos open-source locais'}\n];\ndocument.getElementById('skills-list').innerHTML = skills.map(s=>`<li>${s}</li>`).join('');\ndocument.getElementById('projects-grid').innerHTML = projects.map(p=>`<div class='card'><h3>${p.title}</h3><p>${p.desc}</p></div>`).join('');\n</script>"}}}]},
    {"role": "tool", "content": "{\"success\": true, \"path\": \"index.html\", \"bytes\": 1890}", "name": "append_file"},
    {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "python3 -m http.server 8200 --directory . > /tmp/server.log 2>&1 &"}}}]},
    {"role": "tool", "content": "", "name": "run_bash"},
    {"role": "assistant", "content": "PÁGINA PUBLICADA em http://localhost:8200\n\nSite de portfólio criado com 3 seções (hero, skills, projetos). HTML base + CSS + JS separados em 3 chamadas para evitar arquivos grandes. Paleta escura #0D1117/#58A6FF conforme pedido."}
  ]
}
```

---

## CATEGORIA 2 — code_analysis_report (35 exemplos)

**Problema que resolve:** F5 (24% vs 71%). Após ler código com run_bash/read_file (10 turns),
modelo não produzia os arquivos de relatório (code_review.md, plano_correcoes.md, quality_report.md).

**Padrão obrigatório:**
```
user: "Analise [codebase/módulo] e produza [relatório]"
assistant: run_bash(command="ls -la / find ...") → explorar estrutura
tool: [resultado do ls/find]
assistant: read_file(path="arquivo.py") → ler código
tool: [conteúdo do arquivo]
assistant: [0-2 chamadas adicionais de run_bash/read_file para análise completa]
assistant: write_file(path="code_review.md", content="# Code Review\n## Pontos Positivos\n...")
tool: {"success": true}
assistant: write_file(path="plano_correcoes.md", content="# Plano de Correções\n...")
tool: {"success": true}
assistant: "REVISÃO CONCLUÍDA. Relatórios gerados: code_review.md e plano_correcoes.md."
```

**Subcategorias (35 exemplos total):**
- `code_review_report` (15 ex): análise de módulos Python + code_review.md + plano_correcoes.md
  - DEVE: ler ao menos 1 arquivo com read_file, escrever pelo menos 2 arquivos de relatório
  - Frases obrigatórias: "REVISÃO CONCLUÍDA" na resposta final
  - Relatórios com seções reais: Pontos Positivos, Problemas Críticos, Melhorias Sugeridas

- `quality_report` (10 ex): análise de qualidade → quality_report.md
  - DEVE incluir seções: Resumo Executivo, Métricas, Riscos, Recomendações
  - Frase obrigatória: "ANÁLISE CONCLUÍDA" na resposta final

- `architecture_analysis` (10 ex): análise de arquitetura de sistema → architecture.md
  - DEVE explorar estrutura de diretórios com run_bash antes de escrever
  - Frase obrigatória: "ANÁLISE CONCLUÍDA" ou "REVISÃO CONCLUÍDA"

---

## CATEGORIA 3 — pytest_isolation (25 exemplos)

**Problema que resolve:** P3 (67% vs 93%). Testes pytest falham por shared state entre funções
de teste (ex: `sqlite3.OperationalError: table already exists` na segunda função de teste).

**Padrão obrigatório:**
```python
# ERRADO (o que o modelo gerava):
def test_funcao_a():
    conn = sqlite3.connect("db.sqlite3")
    conn.execute("CREATE TABLE foo ...")  # ← cria tabela
    ...

def test_funcao_b():
    conn = sqlite3.connect("db.sqlite3")
    conn.execute("CREATE TABLE foo ...")  # ← OperationalError: table already exists

# CORRETO (o que o modelo deve gerar):
import pytest, sqlite3, tempfile, os

@pytest.fixture
def db_path(tmp_path):
    """Banco temporário isolado por test."""
    return str(tmp_path / "test.db")

def test_funcao_a(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foo ...")
    ...

def test_funcao_b(db_path):
    conn = sqlite3.connect(db_path)  # novo banco limpo por test
    conn.execute("CREATE TABLE foo ...")
    ...
```

**Subcategorias (25 exemplos total):**
- `pytest_sqlite_isolation` (15 ex): ferramentas Python com SQLite + testes isolados via tmp_path
  - DEVE: usar `@pytest.fixture` com `tmp_path` para isolar estado entre testes
  - DEVE: verificar com read_file antes de escrever o teste que o nome da função bate com o módulo
  - Testes devem passar (sem import errors, sem shared state)

- `pytest_file_isolation` (10 ex): ferramentas Python com sistema de arquivos + testes isolados
  - DEVE: usar `tmp_path` fixture para criar arquivos temporários por test
  - DEVE: cleanup implícito (tmp_path é descartado automaticamente pelo pytest)

---

## CATEGORIA 4 — completion_signals_forge (20 exemplos)

**Problema que resolve:** F3 (94% vs 100%) e guardrail loop insuficiente.
Headings exatos e frases de conclusão nas respostas.

**Subcategorias (20 exemplos total):**
- `market_analysis_signals` (10 ex): relatórios de mercado com headings EXATOS
  - OBRIGATÓRIO: seção `## COTAÇÕES` (exatamente assim, maiúsculas)
  - OBRIGATÓRIO: seção `## RECOMENDAÇÃO` (exatamente assim, maiúsculas)
  - OBRIGATÓRIO: frase `ANÁLISE CONCLUÍDA` no final da resposta (sem ponto, sem variação)

- `completion_after_reflection` (10 ex): exemplos onde must_compliance roda e modelo corrige
  - Simula: assistente emite resposta sem frase obrigatória → engine injeta must_compliance →
    modelo corrige incluindo frase
  - Formato: assistant(sem frase) → user(engine injection "mandatory rules not met") →
    assistant(com frase exata)

---

## CATEGORIA 5 — general_reasoning (20 exemplos)

**Problema que resolve:** Catastrophic forgetting. Dataset V2 era 100% agentic, modelo perdeu
capacidade de raciocínio livre. Esta categoria não usa tools.

**Subcategorias (20 exemplos total):**
- `technical_analysis_no_tool` (10 ex): análise técnica profunda sem tool calls
  - Tópicos: trade-offs de arquitetura, comparação de algoritmos, análise de performance,
    decisões de design em sistemas de IA, comparação de abordagens de fine-tuning
  - NÃO usar tools. Resposta longa (300-600 palavras) e estruturada com markdown
  - Usuário é desenvolvedor avançado (não explicar conceitos básicos)

- `code_explanation_no_tool` (10 ex): explicação de código/algoritmo sem tool calls
  - Tópicos: explicar como funciona um algoritmo, revisar uma abordagem, sugerir melhorias
  - NÃO usar tools. Incluir trechos de código nas respostas quando relevante
  - Resposta direta e técnica, PT-BR

---

## CATEGORIA 6 — tool_generalization (160 exemplos)

**Objetivo:** Ensinar o modelo a operar como agente generalista no AgentForge. O engine passa o
schema completo de cada tool (name, description, parameters, when_to_use) a cada chamada. O modelo
deve ser capaz de usar qualquer tool nova baseado apenas no schema, sem ter sido treinado nela antes.

**Por que isso é crítico:** AgentForge cria tools, skills e agents dinamicamente. O modelo vai
encontrar tools que não existiam quando foi treinado — precisa saber raciocinar sobre schemas.

### Subcategoria 6.1 — schema_driven_use (50 exemplos)

O modelo recebe uma tool com nome inventado/incomum e a usa corretamente baseado apenas na description e parameters.

**Padrão:**
```
system: "Você é um agente AgentForge. Tools disponíveis: [tool com nome incomum, description clara]"
user: "Faça X"
→ model: usa a tool corretamente baseado no schema, sem hesitar
→ tool: resultado simulado realista
→ model: resposta final que incorpora o resultado
```

**Exemplos de tools incomuns a usar:**
- `harvest_metrics(source: str, since: str) → dict` — coleta métricas
- `diff_snapshots(before: str, after: str) → str` — compara estados
- `emit_webhook(url: str, payload: dict) → bool` — dispara webhook
- `chunk_text(text: str, max_tokens: int) → list` — divide texto
- `score_relevance(query: str, docs: list) → list` — rank documentos
- `extract_entities(text: str, types: list) → dict` — NER
- `pin_memory(key: str, value: str, ttl_hours: int) → bool` — grava memória
- `resolve_alias(alias: str) → str` — resolve nome para caminho real
- `schedule_task(cron: str, agent_dir: str, input: str) → str` — agenda agente
- `validate_schema(data: dict, schema: dict) → list[str]` — valida dados

**Regras:**
- O modelo NUNCA questiona "essa tool existe?" — usa diretamente baseado no schema
- A description da tool é suficiente para o modelo entender o que fazer
- Gerar 5 exemplos por tool (10 tools × 5 = 50 exemplos)

### Subcategoria 6.2 — tool_discovery (40 exemplos)

O modelo não sabe quais tools estão disponíveis e as descobre via run_bash antes de agir.

**Padrão:**
```
system: "Você é um agente AgentForge com acesso a run_bash e read_file."
user: "Faça X usando as tools disponíveis"
→ model: run_bash("ls ~/.agentforge/tools/ 2>/dev/null || ls ./tools/ 2>/dev/null")
→ tool: ["fetch_news.py", "summarize_text.py", "post_social.py"]
→ model: read_file("tools/fetch_news.py")
→ tool: [conteúdo do arquivo — class ToolSpec + description]
→ model: [chama a tool que descobriu, usando o schema lido]
→ tool: resultado
→ model: resposta final
```

**Tópicos de tarefas (o agente descobre a tool certa):**
- Buscar e resumir notícias técnicas
- Processar logs e gerar relatório
- Enviar notificação quando tarefa concluída
- Escanear diretório e extrair metadados
- Verificar saúde de serviços e registrar resultado
- Criar novo agente e testá-lo
- Fazer backup de arquivo antes de modificar
- Traduzir texto usando tool local

### Subcategoria 6.3 — create_then_use (40 exemplos)

O modelo cria uma nova tool/skill via write_file + register_tool_file e depois a usa na mesma sessão.

**Padrão:**
```
user: "Preciso de uma tool que faça X. Crie e use."
→ model: write_file("tools/my_tool.py", """
    from agentforge.tools.registry import ToolSpec
    def my_tool(param: str) -> str: ...
    SPEC = ToolSpec(name="my_tool", description="...", ...)
""")
→ tool: {"success": true}
→ model: run_bash("python3 -c 'from tools.my_tool import SPEC; print(SPEC.name)'")
→ tool: "my_tool"
→ model: [invoca my_tool(param="...") — a tool que acabou de criar]
→ tool: resultado
→ model: "Tool criada e testada. Resultado: ..."
```

**Tipos de tools a criar e usar:**
- Parser de formato específico (CSV, YAML, log customizado)
- Calculadora de métrica específica (latência P99, custo por token)
- Wrapper de API externa (clima, câmbio, notícias)
- Ferramenta de análise de texto (contagem, frequência, sentiment simples)
- Tool de manipulação de arquivo (converter, comprimir, filtrar)

### Subcategoria 6.4 — error_recovery_tool (30 exemplos)

O modelo tenta usar uma tool, recebe erro, e se adapta para completar a tarefa.

**Padrão:**
```
→ model: chama tool_x(...)
→ tool: "Error: tool 'tool_x' not found in registry"
→ model: run_bash("ls tools/") → descobre alternativa
→ model: chama tool_y(...) — alternativa com mesma função
→ tool: resultado correto
→ model: resposta final que menciona que usou tool_y como fallback
```

**Tipos de erro a simular:**
- Tool not found → descobrir alternativa via ls
- Parâmetro errado → ler schema com read_file e corrigir
- Tool retorna erro de permissão → tentar com sudo ou path alternativo
- Tool retorna dados vazios → tentar outra fonte/abordagem
- Timeout → dividir em chamadas menores

---

## Distribuição total

| Categoria | Subcategoria | Volume | Gap alvo |
|---|---|---|---|
| write_large_file | write_large_file_site | 20 | F1: +15pt |
| write_large_file | write_large_file_report | 20 | F1/F5 geral |
| code_analysis_report | code_review_report | 15 | F5: +8pt |
| code_analysis_report | quality_report | 10 | F5: +3pt |
| code_analysis_report | architecture_analysis | 10 | F5: +2pt |
| pytest_isolation | pytest_sqlite_isolation | 15 | P3: +3pt |
| pytest_isolation | pytest_file_isolation | 10 | P3: +1pt |
| completion_signals_forge | market_analysis_signals | 10 | F3: +1pt |
| completion_signals_forge | completion_after_reflection | 10 | F3/geral |
| general_reasoning | technical_analysis_no_tool | 10 | forgetting |
| general_reasoning | code_explanation_no_tool | 10 | forgetting |
| **tool_generalization** | schema_driven_use | 50 | generalização |
| **tool_generalization** | tool_discovery | 40 | generalização |
| **tool_generalization** | create_then_use | 40 | generalização |
| **tool_generalization** | error_recovery_tool | 30 | generalização |
| **TOTAL** | | **300** | |

---

## Instruções para o gerador (Agy)

Ao gerar cada exemplo:
1. Escolha IDs sequenciais (v3-c001, v3-c002, ...)
2. O campo system DEVE refletir o contexto do cenário (FORGE ou REAL)
3. tool_calls[].function.arguments é sempre dict (nunca string JSON)
4. role tool sempre tem campo "name" com o nome da ferramenta
5. Nunca coloque newlines literais dentro de strings JSON — use \n
6. O conteúdo de write_file/append_file NUNCA deve exceder 4KB por chamada
7. Para write_large_file: obrigatório pelo menos 3 chamadas (write_file + 2 append_file)
8. Para code_analysis_report: obrigatório pelo menos 1 read_file E pelo menos 1 write_file de relatório
9. Para pytest_isolation: os testes DEVEM usar @pytest.fixture com tmp_path
10. Valide: última mensagem é sempre role=assistant com conteúdo de texto
