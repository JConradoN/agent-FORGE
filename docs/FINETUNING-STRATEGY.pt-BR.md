# Fine-Tuning qwen3.5 para AgentForge

## Motivação

O AgentForge foi otimizado para a família qwen3.5. O próximo nível é o inverso: especializar o próprio modelo para o framework, eliminando as falhas residuais que nenhum prompt consegue corrigir de forma confiável.

Falhas residuais identificadas nos benchmarks (junho/2026):
1. **Incoerência entre tool calls** — gera `search_memory` na impl e `_search_shared_memory` no teste
2. **Casing inconsistente em mensagens de erro** — `"Query cannot be empty"` vs match `"query"`
3. **Frase de confirmação omitida** — ignora instrução de formato do output final
4. **XML leakage** — 27b vaza `<tool_use>` tags no output textual

Essas falhas são estruturais: acontecem mesmo com guardrails, even com prompts muito explícitos. Fine-tuning é a solução correta porque o problema é de distribuição aprendida, não de falta de instrução.

---

## Estratégia

### Fase 1 — Coleta de Dados (Golden Runs)

Gerar exemplos de "runs perfeitos" usando um modelo teacher forte (Claude claude-sonnet-4-6 via API). O teacher executa cada cenário e produz a sequência correta de tool calls + output final.

```bash
# Rodar cenários com o teacher (Claude API)
python3 scripts/generate_training_data.py \
    --scenarios P3 P4 F3 \
    --teacher claude-sonnet-4-6 \
    --runs-per-scenario 10 \
    --output training_data/golden_runs.jsonl
```

Cada exemplo tem o formato de conversa multi-turn com tool calls:

```json
{
  "messages": [
    {"role": "system", "content": "<system_prompt do agente>"},
    {"role": "user", "content": "<prompt do cenário>"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"type": "function", "function": {"name": "write_file", "arguments": {...}}}]},
    {"role": "tool", "content": "escrito: memory_search.py (2341 chars)", "tool_call_id": "c1"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"type": "function", "function": {"name": "read_file", "arguments": {"path": "memory_search.py"}}}]},
    {"role": "tool", "content": "<conteúdo do arquivo>", "tool_call_id": "c2"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"type": "function", "function": {"name": "write_file", "arguments": {...}}}]},
    {"role": "tool", "content": "escrito: test_memory_search.py (3100 chars)", "tool_call_id": "c3"},
    {"role": "assistant", "content": null,
     "tool_calls": [{"type": "function", "function": {"name": "run_bash", "arguments": {"command": "python3 -m pytest test_memory_search.py -v"}}}]},
    {"role": "tool", "content": "8 passed in 0.05s", "tool_call_id": "c4"},
    {"role": "assistant", "content": "TOOL CRIADO: memory_search.py + 8 testes passando"}
  ]
}
```

**Volume alvo:** 50-100 exemplos por cenário = 150-300 total. Pequeno o suficiente para treinar em 2-4h com LoRA no fox-server.

### Fase 2 — Augmentation (Variações Sintéticas)

A partir dos golden runs, gerar variações:
- Diferentes nomes de função (mas sempre consistentes entre impl e teste)
- Diferentes mensagens de erro (mas sempre lowercase para match)
- Diferentes conteúdos de relatório (mas sempre com as frases de confirmação)

Isso aumenta o dataset 5-10x sem custo de API.

### Fase 3 — Fine-Tuning com LoRA

**Ferramentas recomendadas:**
- `unsloth` — LoRA otimizado para Qwen3, roda no fox-server com 24 GB VRAM
- `axolotl` — alternativa mais configurável

**Configuração LoRA para qwen3.5:9b:**
```yaml
base_model: Qwen/Qwen3.5-7B-Instruct  # equivalente ao 9b do Ollama
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

load_in_4bit: true
adapter: lora
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - v_proj
  - k_proj
  - o_proj

datasets:
  - path: training_data/golden_runs.jsonl
    type: chat_template
    chat_template: qwen3

sequence_len: 8192
micro_batch_size: 1
gradient_accumulation_steps: 4
num_epochs: 3
learning_rate: 2e-4
```

**VRAM necessária:**
- qwen3.5:9b + LoRA 4-bit: ~14 GB → cabe em 1 RTX 3060 12 GB com gradient checkpointing
- qwen3.5:27b + LoRA 4-bit: ~20 GB → cabe nos 24 GB combinados (2× RTX 3060)

### Fase 4 — Exportar para Ollama

Após treinar, exportar o adaptador LoRA como Modelfile Ollama:

```bash
# Merge LoRA weights
python3 scripts/merge_lora.py \
    --base Qwen/Qwen3.5-7B-Instruct \
    --adapter training_data/lora_output \
    --output training_data/qwen35-agentforge-9b

# Criar Modelfile
cat > Modelfile << 'EOF'
FROM training_data/qwen35-agentforge-9b
PARAMETER temperature 0
PARAMETER num_predict -1
SYSTEM "Você é um agente AgentForge especializado em tool calling. Siga sempre as instruções de formato de output."
EOF

ollama create qwen35-agentforge:9b -f Modelfile
```

---

## Dados de Treinamento — O que Capturar

### O que queremos ensinar

| Comportamento | Exemplo de treino |
|---|---|
| **Coerência entre tool calls** | Write impl → read_file → Write tests (names match) |
| **Frase de confirmação** | Output sempre termina com 'TOOL CRIADO' / 'SKILL CRIADA' |
| **Fetch antes de analisar** | http_get × 3 → write_file (nunca o inverso) |
| **Sem XML leakage** | Output final nunca contém `<tool_use>` |
| **Recovery de erro** | pytest falha → lê output → corrige código (não repete mesmo pytest) |

### Formato de captura dos runs atuais

Os runs já salvos em `agents/*/runs.jsonl` têm apenas input/output, sem o histórico completo de tool calls. Precisamos de um formato estendido:

```python
# Adicionar ao engine: captura de conversação completa
def _log_run_extended(self, messages: list[dict], tool_results_log: list[dict]):
    """Salva o histórico completo para uso como dado de fine-tuning."""
    ...
```

---

## Métricas de Avaliação do Modelo Treinado

Usar o próprio benchmark como test set:

| Cenário | Baseline (qwen3.5:27b) | Meta pós-FT |
|---|---|---|
| FORGE F3 | 94.4% | ≥ 97% |
| REAL P3 | 66.7% | ≥ 85% |
| REAL P4 | 91.7% | ≥ 97% |

O P3 é o mais importante: sair de 66.7% para 85%+ exige coerência entre tool calls — exatamente o que o fine-tuning ensina.

---

## Cronograma Estimado

| Etapa | Esforço | Dependência |
|---|---|---|
| Script de coleta (teacher runs) | 1 dia | Claude API key |
| Coleta dos dados (50 runs × 3 cenários) | ~3h de API | |
| Augmentation sintética | 0.5 dia | |
| Setup Unsloth no fox-server | 0.5 dia | |
| Fine-tuning qwen3.5:9b (3 epochs) | ~4h de GPU | |
| Exportação e teste no Ollama | 1 dia | |
| Benchmark final | ~2h | |
| **Total** | **~3-4 dias** | |

---

## Referências

- [Unsloth — Qwen3 LoRA](https://github.com/unslothai/unsloth)
- [Axolotl — tool call fine-tuning](https://github.com/OpenAccess-AI-Collective/axolotl)
- [Qwen3 fine-tuning guide](https://qwen.readthedocs.io/en/latest/training/SFT/)
- Benchmarks base: `~/repos/estudo/agent-benchmark-suite/` (ABS), `~/repos/estudo/real/` (REAL)
