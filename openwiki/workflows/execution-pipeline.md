# Execution Pipeline

## Overview

The execution pipeline is implemented in `AgentRuntime.run()` within `src/agentforge/runtime/engine.py`. It orchestrates the full lifecycle of an agent run: from loading the spec to returning the final result.

## Pipeline Stages

```
run(input_text)
  │
  ├─ 1. Build system prompt from system_prompt.md
  │
  ├─ 2. Tool calling cycle (respond_or_tool mode)
  │     ├── Inference with tool schema
  │     ├── Pushback: redirect model to use tools
  │     ├── Execute tool calls
  │     ├── Loop guard: detect stuck cycles
  │     └── Exhaust cycles → final inference
  │
  ├─ 3. Guardrails check
  │     ├── must_not: auto-correct violations (up to 2 retries)
  │     └── must: deterministic phrase match + LLM judge
  │
  ├─ 4. Reflection (if rounds > 0)
  │     └── N rounds of self-critique
  │
  ├─ 5. Memory persistence (if enabled)
  │     └── save_history()
  │
  └─ 6. Return result
        ├── agent_id
        ├── output
        ├── metadata (latency_ms, timestamp, tool_results, guardrail_violations)
```

## Stage 1: System Prompt

The system prompt is read from `system_prompt.md` (generated from the spec). It contains:
- Agent identity and purpose
- Persona constraints (tone, style)
- Mandatory and forbidden behaviors
- Available tools with descriptions and decision hints
- Memory policy and output format
- Model and workflow policy

## Stage 2: Tool Calling Cycle

### Mode: `respond_or_tool`

When the workflow mode is `respond_or_tool`, the engine enters a multi-cycle tool calling loop:

```
for cycle in range(max_tool_cycles):
    1. Call provider.generate(tools_schema=...)
    2. If NO tool_calls and tools available → pushback (up to 2 times)
    3. If NO tool_calls and no pushback left → return response
    4. For each tool_call:
       a. Execute tool via execute_tool()
       b. Inject result into history
       c. Check loop guard
    5. If loop detected → break
```

### Pushback

If tools are available and the model hasn't used any yet, the engine pushes back:
1. Appends the model's direct response as assistant message
2. Appends a user message: "You have not used any tools yet. Do NOT output code or text directly — use the available tools to complete the task. Call the appropriate tool now to proceed."
3. Continues to next cycle
4. Maximum 2 pushback attempts — after that, the direct response is accepted

### Loop Guard

The loop guard tracks recent (tool, args_hash, result_hash) triplets. A window of 5 entries is maintained. If all 5 entries are identical (same call, same unchanged result), the loop is detected and the cycle aborts.

Key detail: the guard compares **tool + args + result**, not just tool + args. This allows legitimate polling of async operations (e.g., `heygen_get_agent_session` where the session status changes each call) to survive.

### Final Inference

When cycles are exhausted or a loop is detected, the engine performs a final inference:
- Appends a completion hint with summary of executed tools
- Includes quoted phrases from `must` rules as completion hints
- Calls provider.generate WITHOUT tools_schema (produces final text response)

### Tool Schema Construction

The `_build_tools_schema()` method converts `ToolSpec` objects to OpenAI/Ollama function format:
- For each tool: `type: "function"` with `function.name`, `function.description`, `function.parameters`
- `when_to_use` and `when_not_to_use` are appended to the description as decision hints
- `input_schema` JSON is parsed into the `parameters` field
- If the agent has declared workers (`workflow.agents`), `run_agent` is injected as a tool with a description listing all available workers

### Ollama-Specific Handling

The `OllamaProvider` in `src/agentforge/providers/ollama.py` has several special handling paths:

1. **think:False**: Always sent in chat payloads to disable Qwen3 thinking mode (avoids empty `message.content`).
2. **thinking fallback**: If `message.content` is empty and `message.thinking` exists, the thinking text is used as output.
3. **Regex fallback for tool calls**: If the Ollama API doesn't return tool_calls in the response, two regex patterns try to extract tool calls from the output text:
   - Pattern 1: `tool_name({"arg": "val"})` — function call format
   - Pattern 2: JSON blocks with `name`/`arguments` or `tool`/`args` fields

### Mode: Non-tool-calling

For modes other than `respond_or_tool`, the engine calls the provider once with the system prompt and input, then returns the output directly.

## Stage 3: Guardrails Check

### must_not Rules (Auto-Correct)

After the main output is generated, the engine:
1. Checks if the output (or the last `write_file` content) violates any `must_not` rules
2. The check uses the model itself as judge: sends the rules + output text and asks which rules were violated
3. If violations found: sends a correction prompt and re-generates (up to 2 retries)
4. If the agent persisted output via `write_file`, the correction is re-written to disk

### must Rules (Compliance Check)

The engine checks `must` rules in two ways:

1. **Quoted-phrase rules**: Rules containing quoted phrases (e.g., `'ANÁLISE CONCLUÍDA'`) are checked via substring match against the output text and tool execution evidence.
2. **Open rules**: Rules without quotes are checked via LLM judge with the output text and tool execution summary.

Unmet rules are returned in the result metadata but do NOT trigger correction (only `must_not` does).

## Stage 4: Reflection

If `reflection_rounds > 0`, the engine runs N rounds of self-critique:

Each round:
1. Sends the original input + current output to the model
2. Asks: Is it complete and accurate? Does it respect role restrictions? Can it be more objective?
3. Uses the model's refined output for the next round
4. Returns the final refined output

Reflection is stateless (no conversation history) and runs sequentially.

## Stage 5: Memory Persistence

If memory is enabled:
1. History is loaded at the start via `load_history()`
2. The `apply_window()` function applies the configured policy (truncate or summarize) based on `max_turns`
3. At the end, history is saved via `save_history()` to `history.json` in the agent directory

Memory type affects whether history is loaded/persisted. `memory_type: "none"` skips all persistence.

## Stage 6: Result

The engine returns a dict:
```json
{
  "agent_id": "lab-ops",
  "output": "Final response text",
  "metadata": {
    "latency_ms": 12345,
    "timestamp": "2026-07-09T...",
    "tool_results": [...],
    "guardrail_violations": []
  }
}
```

## Key Source References

| File | Role |
|------|------|
| `src/agentforge/runtime/engine.py` | `AgentRuntime` class — full pipeline implementation |
| `src/agentforge/runtime/memory.py` | `load_history`, `save_history`, `apply_window`, `apply_limit_summarize` |
| `src/agentforge/runtime/mem0_hook.py` | Hook for LLM-based summarizers |
| `src/agentforge/providers/base.py` | `ProviderRequest`, `ProviderResponse` data models |
| `src/agentforge/providers/ollama.py` | `OllamaProvider` — Ollama API integration with special handling |
| `src/agentforge/tools/registry.py` | `execute_tool`, `register_tool`, `get_tool` |
| `src/agentforge/core/agent_models.py` | `ToolSpec`, `WorkflowSpec`, `GuardrailSpec` models |
