# Tool Registry — Agentes que Constroem Ferramentas

## Visão Geral

O **Tool Registry** é o mecanismo pelo qual o AgentForge se auto-estende: agentes criam novas ferramentas Python durante a execução, as testam com pytest e as registram permanentemente no framework. Na próxima vez que qualquer agente inicializar, as ferramentas registradas estarão disponíveis como se fossem builtins.

Isso implementa o padrão **Voyager** (NVIDIA, 2023) para agentes locais: acúmulo progressivo de skills geradas pelo próprio sistema.

---

## Arquitetura

```
agents-framework/
├── tool_registry/                 ← Ferramentas geradas por agentes
│   ├── registry.yaml              ← Manifesto persistente
│   └── search_memory.py           ← Exemplo: criada pelo tool-builder
│
├── src/agentforge/tools/
│   ├── register_tool_file.py      ← Tool builtin: registra arquivos no registry
│   ├── dynamic_loader.py          ← Carrega registry.yaml ao inicializar
│   └── registry.py                ← Registry principal (builtins + dinâmicas)
│
└── agents/tool-builder/           ← Agente especializado em criar tools
    └── agent.yaml
```

### Fluxo de criação

```
1. tool-builder recebe descrição de ferramenta
        ↓
2. Escreve <tool>.py com write_file
        ↓
3. Lê implementação com read_file (verificação de coerência)
        ↓
4. Escreve test_<tool>.py com write_file
        ↓
5. Executa pytest com run_bash (validação real)
        ↓
6. Se testes passam: chama register_tool_file
        ↓
7. tool_registry/<tool>.py + registry.yaml atualizados
        ↓
8. Tool disponível imediatamente (processo atual) e em toda sessão futura
```

### Carregamento automático

Ao inicializar, `_register_builtin_tools()` em `registry.py` chama `load_dynamic_tools()`, que lê `registry.yaml` e importa cada arquivo Python dinamicamente. Ferramentas registradas têm o mesmo status que builtins — qualquer agente pode usá-las declarando o nome no `agent.yaml`.

```python
# src/agentforge/tools/dynamic_loader.py
def load_dynamic_tools() -> list[str]:
    """Carrega tools registradas em tool_registry/registry.yaml para o _ToolRegistry vivo."""
```

---

## registry.yaml

Manifesto persistente de todas as ferramentas registradas. Não editar manualmente — gerenciado pelo `register_tool_file`.

```yaml
tools:
  - name: search_memory
    file: search_memory.py
    function: search_memory
    description: Busca na agent-mesh shared_memory por query LIKE no key e value.
    input_schema: '{"type":"object","properties":{"query":{"type":"string"},"db_path":{"type":"string"}},"required":["query"]}'
    created_by: tool-builder
    registered_at: '2026-06-06T20:14:00.325922+00:00'
```

Campos:

| Campo | Descrição |
|---|---|
| `name` | Nome da tool — usado em `agent.yaml` e no `execute_tool` |
| `file` | Nome do arquivo Python dentro de `tool_registry/` |
| `function` | Nome da função pública a ser exposta |
| `description` | Descrição usada no schema de tools (context para o modelo) |
| `input_schema` | JSON schema dos parâmetros (string JSON) |
| `created_by` | Identificação do agente criador |
| `registered_at` | ISO 8601 UTC |

---

## register_tool_file (builtin)

Ferramenta builtin disponível para qualquer agente. Valida, copia e registra um arquivo Python no registry.

**Parâmetros:**

```python
def register_tool_file(
    source_path: str,      # Caminho relativo ao AGENT_WORKDIR
    tool_name: str,        # Nome snake_case único no registry
    function_name: str,    # Nome da função pública a expor
    description: str,      # Descrição para o schema de tools
    input_schema: str,     # JSON schema como string (default: "{}")
    created_by: str,       # Identificação do criador (default: "tool-builder")
) -> dict
```

**Retorno em caso de sucesso:**

```json
{
  "success": true,
  "tool_name": "search_memory",
  "registry_path": "/home/user/agents-framework/tool_registry/search_memory.py",
  "message": "Tool 'search_memory' registrada com sucesso em tool_registry/"
}
```

**Validações executadas antes de registrar:**

1. Arquivo existe no `AGENT_WORKDIR`
2. Sintaxe Python válida (`ast.parse`)
3. Função pública existe no módulo (`getattr`)
4. Módulo importa sem erros

Se qualquer validação falhar, retorna `{"success": false, "error": "<motivo>"}` sem tocar o registry.

---

## Agente tool-builder

Agente especializado em criar e registrar ferramentas. Localizado em `agents/tool-builder/`.

**Modelo:** `qwen3.5:27b` (padrão — tarefas de código multi-step)

**Tools disponíveis:** `write_file`, `read_file`, `run_bash`, `register_tool_file`

**Guardrails:**
- `must`: reler a implementação antes de escrever testes; executar pytest antes de registrar; registrar somente com testes passando
- `must_not`: registrar com testes falhando; inventar que pytest passou

**Uso via CLI:**

```bash
agentforge run --agent-dir agents/tool-builder --input "
Crie uma tool Python chamada rate_limiter que:
- Recebe (key: str, limit: int, window_s: int) -> bool
- Usa Redis local para controle de janela deslizante
- Testa com pytest usando Redis mockado
- Registra no framework após testes passarem
"
```

**Uso programático:**

```python
from agentforge.runtime.engine import AgentRuntime
import os

os.environ["AGENT_WORKDIR"] = "/tmp/my_tool_build"
runtime = AgentRuntime.from_agent_dir("agents/tool-builder")
result = runtime.run("Crie uma tool ...")
```

---

## Usando tools registradas em outros agentes

Depois de registrada, a tool aparece no `_ToolRegistry` com seu `tool_name`. Para usá-la em qualquer agente, declare no `agent.yaml`:

```yaml
tools:
  - name: search_memory
    description: Busca na agent-mesh shared_memory por query LIKE no key e value.
    when_to_use: "Usar quando precisar recuperar contexto de sessões anteriores."
    input_schema: '{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}'
```

O engine gera o schema correto para o Ollama — o modelo decide quando chamar.

---

## Tools registradas (junho/2026)

| Tool | Criada por | Descrição |
|---|---|---|
| `search_memory` | tool-builder + human-fix | Busca na `shared_memory` do `agent-mesh` por LIKE em key e value. Conecta a `~/.agent-mesh/state.db`. |

---

## Limitações e próximos passos

### Limitações atuais

- O modelo (`qwen3.5:27b`) completa ~80% do fluxo de forma autônoma. Os 20% restantes (erros de schema entre arquivos separados) requerem revisão humana ou fine-tuning.
- Cada `register_tool_file` sobrescreve a versão anterior da tool — não há versionamento.
- Tools dinâmicas não são validadas a cada startup — apenas carregadas. Se o arquivo `tool_registry/*.py` corrompeu, o erro é silencioso.

### Próximos passos

- **Fine-tuning**: usar o `docs/FINETUNING-STRATEGY.md` para treinar qwen3.5 a completar 100% do fluxo sem intervenção
- **Versionamento**: `registry.yaml` armazenar histórico de versões (semver simples)
- **Validação no startup**: `load_dynamic_tools` verificar sintaxe antes de registrar
- **Tool discovery**: CLI `agentforge tools list` para listar builtins + dinâmicas

---

## Referências

- [Voyager: An Open-Ended Embodied Agent with Large Language Models](https://arxiv.org/abs/2305.16291) — inspiração arquitetural
- [`docs/MODEL-STRATEGY.md`](MODEL-STRATEGY.md) — critérios de seleção do modelo
- [`docs/FINETUNING-STRATEGY.md`](FINETUNING-STRATEGY.md) — estratégia de fine-tuning para atingir 100% de autonomia
