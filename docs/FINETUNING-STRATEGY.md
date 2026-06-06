# Fine-Tuning qwen3.5 for AgentForge

## Motivation

AgentForge has been optimized for the qwen3.5 family. The next level is the inverse: specializing the model itself for the framework, eliminating the residual failures that no prompt can reliably fix.

Residual failures identified in the benchmarks (June 2026):
1. **Incoherence between tool calls** — generates `search_memory` in the impl and `_search_shared_memory` in the test
2. **Inconsistent casing in error messages** — `"Query cannot be empty"` vs match on `"query"`
3. **Missing confirmation phrase** — ignores the final output format instruction
4. **XML leakage** — 27b leaks `<tool_use>` tags into textual output

These failures are structural: they occur even with guardrails, even with very explicit prompts. Fine-tuning is the correct solution because the problem is one of learned distribution, not missing instruction.

---

## Strategy

### Phase 1 — Data Collection (Golden Runs)

Generate examples of "perfect runs" using a strong teacher model (Claude claude-sonnet-4-6 via API). The teacher executes each scenario and produces the correct sequence of tool calls + final output.

```bash
# Run scenarios with the teacher (Claude API)
python3 scripts/generate_training_data.py \
    --scenarios P3 P4 F3 \
    --teacher claude-sonnet-4-6 \
    --runs-per-scenario 10 \
    --output training_data/golden_runs.jsonl
```

Each example uses the multi-turn conversation format with tool calls:

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

**Target volume:** 50-100 examples per scenario = 150-300 total. Small enough to train in 2-4h with LoRA on the test hardware.

### Phase 2 — Augmentation (Synthetic Variations)

From the golden runs, generate variations:
- Different function names (but always consistent between impl and test)
- Different error messages (but always lowercase for matching)
- Different report contents (but always including the confirmation phrases)

This multiplies the dataset 5-10x at no API cost.

### Phase 3 — Fine-Tuning with LoRA

**Recommended tools:**
- `unsloth` — LoRA optimized for Qwen3, runs on the test hardware with 24 GB VRAM
- `axolotl` — more configurable alternative

**LoRA configuration for qwen3.5:9b:**
```yaml
base_model: Qwen/Qwen3.5-7B-Instruct  # equivalent to Ollama's 9b
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

**Required VRAM:**
- qwen3.5:9b + LoRA 4-bit: ~14 GB → fits in 1 RTX 3060 12 GB with gradient checkpointing
- qwen3.5:27b + LoRA 4-bit: ~20 GB → fits in the combined 24 GB (2× RTX 3060)

### Phase 4 — Export to Ollama

After training, export the LoRA adapter as an Ollama Modelfile:

```bash
# Merge LoRA weights
python3 scripts/merge_lora.py \
    --base Qwen/Qwen3.5-7B-Instruct \
    --adapter training_data/lora_output \
    --output training_data/qwen35-agentforge-9b

# Create Modelfile
cat > Modelfile << 'EOF'
FROM training_data/qwen35-agentforge-9b
PARAMETER temperature 0
PARAMETER num_predict -1
SYSTEM "Você é um agente AgentForge especializado em tool calling. Siga sempre as instruções de formato de output."
EOF

ollama create qwen35-agentforge:9b -f Modelfile
```

---

## Training Data — What to Capture

### What we want to teach

| Behavior | Training example |
|---|---|
| **Coherence between tool calls** | Write impl → read_file → Write tests (names match) |
| **Confirmation phrase** | Output always ends with 'TOOL CRIADO' / 'SKILL CRIADA' |
| **Fetch before analyzing** | http_get × 3 → write_file (never the reverse) |
| **No XML leakage** | Final output never contains `<tool_use>` |
| **Error recovery** | pytest fails → reads output → fixes code (does not repeat the same pytest) |

### Capture format for current runs

The runs already saved in `agents/*/runs.jsonl` only have input/output, without the full tool call history. We need an extended format:

```python
# Add to engine: full conversation capture
def _log_run_extended(self, messages: list[dict], tool_results_log: list[dict]):
    """Saves the complete history for use as fine-tuning data."""
    ...
```

---

## Evaluation Metrics for the Trained Model

Use the benchmark itself as the test set:

| Scenario | Baseline (qwen3.5:27b) | Post-FT target |
|---|---|---|
| FORGE F3 | 94.4% | ≥ 97% |
| REAL P3 | 66.7% | ≥ 85% |
| REAL P4 | 91.7% | ≥ 97% |

P3 is the most important: moving from 66.7% to 85%+ requires coherence between tool calls — exactly what fine-tuning teaches.

---

## Estimated Timeline

| Step | Effort | Dependency |
|---|---|---|
| Collection script (teacher runs) | 1 day | Claude API key |
| Data collection (50 runs × 3 scenarios) | ~3h of API | |
| Synthetic augmentation | 0.5 day | |
| Unsloth setup on test hardware | 0.5 day | |
| Fine-tuning qwen3.5:9b (3 epochs) | ~4h of GPU | |
| Export and testing in Ollama | 1 day | |
| Final benchmark | ~2h | |
| **Total** | **~3-4 days** | |

---

## References

- [Unsloth — Qwen3 LoRA](https://github.com/unslothai/unsloth)
- [Axolotl — tool call fine-tuning](https://github.com/OpenAccess-AI-Collective/axolotl)
- [Qwen3 fine-tuning guide](https://qwen.readthedocs.io/en/latest/training/SFT/)
- Base benchmarks: `~/repos/estudo/agent-benchmark-suite/` (ABS), `~/repos/estudo/real/` (REAL)
