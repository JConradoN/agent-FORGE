# Model Strategy — AgentForge

## Decision

AgentForge was **empirically optimized for the qwen3.5 family** (Alibaba's Qwen 3.5), based on 4 months of systematic benchmarks covering 19 distinct local models.

The framework **works with any model available via Ollama**, but the defaults, runtime parameters, and evaluation scenarios were calibrated for qwen3.5:9b and qwen3.5:27b.

---

## Evidence

The benchmarks underpinning this decision, in chronological order:

| Framework | Scope | qwen3.5 result |
|---|---|---|
| **ABS** (Agent Benchmark Suite) | 23 scenarios, 0-4 scale, 19 models | qwen3.5:27b overall champion |
| **LOP** (Local Ops) | Operational tool use with real fixtures | qwen3.5:27b and 9b in top-4 |
| **FORGE** | Real chained tasks (web, exchange rates, analysis) | F3: 94.4% with 27b |
| **REAL** | Browser, coding, skill gen | P4: 91.7%, F3: 94.4% with 27b |

**Validated thesis:** within well-trained families, scale delivers quality. The qwen3.5 family demonstrated superior consistency in instruction-following, coherence across multiple tool calls, and fidelity to explicit guardrails.

---

## Selection Policy by Complexity

```
qwen3.5:9b  (~7 GB VRAM, ~45 tok/s on test hardware)
└── Simple and intermediate tasks:
    - Monitoring and diagnostics (fox-health, lab-ops)
    - Subtask orchestration with short context
    - Direct queries without multi-step tool use
    - Classification and triage

qwen3.5:27b  (~17 GB VRAM, ~25 tok/s on test hardware)
└── Complex tasks:
    - Coding with real tests (REAL P3)
    - Full technical documentation generation (REAL P4)
    - Multi-step analysis with external APIs (FORGE F3)
    - Orchestration with multiple subordinate agents
    - Any task requiring coherence across 3+ tool calls
```

**Practical criterion:** if the agent needs to maintain coherence of names, types, or contracts across multiple separate `write_file` or `run_bash` calls, use 27b. The 9b tends to introduce subtle inconsistencies (casing differences in error messages, function names with prefix variation).

---

## `think: False` Parameter

Ollama supports the `think` parameter for Qwen3 family models, which activates extended internal reasoning. By default, when not specified, Qwen3 models activate thinking mode and may return an empty `message.content` during the tool calling loop — which causes an error in the provider.

AgentForge explicitly disables thinking mode in chat calls:

```python
# src/agentforge/providers/ollama.py
payload = {
    "model": request.model,
    "messages": messages,
    "stream": False,
    "think": False,  # prevents empty message.content during tool calling
}
```

This ensures deterministic behavior during the tool calling loop. For other models that do not support `think`, the parameter is simply ignored by Ollama.

---

## Using Other Models

The framework runs with any model supported by Ollama. To switch the model for an agent:

```yaml
# agents/<id>/agent.yaml
model_policy:
  default_model: llama3.3:70b   # or any available model
  fallback_model: qwen3.5:9b    # used if the primary fails
```

Or via environment variable in the benchmark script:

```bash
python3 scripts/run_benchmark_eval.py --scenarios P3 --model llama3.3:70b
```

**Note on comparability:** the auto_checks and evaluation criteria for FORGE and REAL scenarios were designed to be model-agnostic (they verify files, Python syntax, pytest results — they do not depend on any model's specific vocabulary). Results are comparable across models.

---

## Results Reference (qwen3.5 — June/2026)

| Scenario | Dimension | 9b | 27b |
|---|---|---|---|
| FORGE F3 | Market analysis (exchange rates + report + Claudio) | 94.4% | 94.4% |
| REAL P3 | Python tool with real tests | 66.7% | 66.7%* |
| REAL P4 | Claude skill generation | 91.7% | 91.7% |

*The 27b passes 7/8 tests (vs 0/8 for 9b), but both lose the 4 points from `python_tests_pass` because 1 test fails due to casing inconsistency in a ValueError message generated between two separate `write_file` calls. The 27b is superior in internal quality even with an identical score.

**Recommendation:** use 27b as the default for production agents whenever VRAM allows (≥17 GB available).
