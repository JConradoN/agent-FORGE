from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from agentforge.core.agent_models import AgentSpec, ToolSpec
from agentforge.core.validation import load_yaml_file, validate_agent_spec
from agentforge.providers.base import BaseProvider, ProviderRequest
from agentforge.providers.registry import get_default_registry
from agentforge.runtime.memory import apply_window, load_history, save_history
from agentforge.tools.registry import execute_tool


from agentforge.research.vault_utils import (
    _normalize_path_name,
    _extract_filename_intent_fuzzy,
    _summarize_scan_output,
    _maybe_compress_tool_output,
    _build_input_with_file_content,
)

_TOOL_PREVIEW_PREFIX = """
<tool_results>
"""


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_version: str
    agent_id: str
    provider: str
    model_default: str
    model_fallback: str | None = None
    workflow_mode: str
    channel_type: str
    memory_enabled: bool
    memory_type: str | None = None
    memory_max_turns: int = 0
    memory_policy: str = "truncate"
    memory_feed_mem0: bool = False
    output_mode: str
    output_format: str | None = None
    conversation_multi_turn: bool = False
    max_tool_cycles: int = 3
    reflection_rounds: int = 0

    @model_validator(mode="before")
    @classmethod
    def _flatten_nested(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        model = values.get("model") or {}
        workflow = values.get("workflow") or {}
        channel = values.get("channel") or {}
        memory = values.get("memory") or {}
        output = values.get("output") or {}
        conversation = values.get("conversation") or {}
        return {
            "runtime_version": values.get("runtime_version", ""),
            "agent_id": values.get("agent_id", ""),
            "provider": __import__("os").environ.get("AGENTFORGE_PROVIDER") or values.get("provider", ""),
            "model_default": __import__("os").environ.get("AGENTFORGE_MODEL") or model.get("default", ""),
            "model_fallback": model.get("fallback"),
            "workflow_mode": workflow.get("mode", ""),
            "channel_type": channel.get("type", ""),
            "memory_enabled": memory.get("enabled", False),
            "memory_type": memory.get("type"),
            "memory_max_turns": memory.get("max_turns", 0),
            "memory_policy": memory.get("policy", "truncate"),
            "memory_feed_mem0": memory.get("feed_mem0", False),
            "output_mode": output.get("mode", ""),
            "output_format": output.get("format"),
            "conversation_multi_turn": conversation.get("multi_turn", False),
            "max_tool_cycles": workflow.get("max_tool_cycles", 3),
            "reflection_rounds": workflow.get("reflection_rounds", 0),
        }


class AgentRuntime:
    def __init__(
        self,
        agent_spec: AgentSpec,
        runtime_config: RuntimeConfig,
        tools: list[ToolSpec],
        root_dir: Path,
    ) -> None:
        self.agent_spec = agent_spec
        self.runtime_config = runtime_config
        self.tools = tools
        self.root_dir = root_dir
        self.logger = logging.getLogger(__name__)

        # Load persisted history if memory is enabled; always start fresh for single-turn.
        if runtime_config.conversation_multi_turn:
            self._history: list[dict[str, str]] = load_history(
                root_dir,
                memory_type=runtime_config.memory_type or "none",
                enabled=runtime_config.memory_enabled,
                max_turns=runtime_config.memory_max_turns,
                policy=runtime_config.memory_policy,
            )
        else:
            self._history = []

    @classmethod
    def from_agent_dir(cls, path: str | Path) -> "AgentRuntime":
        root_dir = Path(path)
        agent_spec = validate_agent_spec(root_dir / "agent.yaml")

        runtime_data = load_yaml_file(root_dir / "runtime.yaml")
        runtime_config = RuntimeConfig.model_validate(runtime_data)

        tools: list[ToolSpec] = []
        tools_yaml = root_dir / "tools.yaml"
        if tools_yaml.exists():
            tools_data = load_yaml_file(tools_yaml)
            tools = [ToolSpec.model_validate(t) for t in (tools_data.get("tools") or [])]

        logging.getLogger(__name__).info(
            "Loaded agent '%s' from %s", agent_spec.agent.id, root_dir
        )
        return cls(
            agent_spec=agent_spec,
            runtime_config=runtime_config,
            tools=tools,
            root_dir=root_dir,
        )

    def _get_provider(self) -> BaseProvider:
        return get_default_registry().create(self.runtime_config.provider)

    def _read_system_prompt(self) -> str | None:
        path = self.root_dir / "system_prompt.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _execute_tool(self, _tool_name: str, **kwargs) -> dict | None:
        return execute_tool(_tool_name, **kwargs)

    def _build_tools_schema(self) -> list[dict]:
        """Converts ToolSpec list to OpenAI/Ollama format.

        If workflow.agents is not empty, injects run_agent as a delegation tool 
        with the list of available workers in the description.
        """
        schema = []
        for tool in self.tools:
            description = tool.description or ""
            if tool.when_to_use:
                description += f" Use when: {tool.when_to_use}."
            if tool.when_not_to_use:
                description += f" Do not use when: {tool.when_not_to_use}."

            # Deriva parâmetros do input_schema se disponível, senão usa schema vazio.
            if tool.input_schema:
                try:
                    params = json.loads(tool.input_schema)
                except (json.JSONDecodeError, TypeError):
                    params = {"type": "object", "properties": {}}
            else:
                params = {"type": "object", "properties": {}}

            schema.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": description,
                    "parameters": params,
                },
            })

        # Injeta run_agent quando há workers declarados no workflow.
        declared_agents = self.agent_spec.workflow.agents
        if declared_agents:
            agents_list = "\n".join(
                f"  - {a.name} (agent_dir={a.agent_dir}): {a.description or 'no description'}"
                for a in declared_agents
            )
            schema.append({
                "type": "function",
                "function": {
                    "name": "run_agent",
                    "description": (
                        "Delegates a task to a specialized agent and returns the output.\n"
                        f"Available agents:\n{agents_list}"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_dir": {
                                "type": "string",
                                "description": "Agent directory (use the agent_dir values listed above)",
                            },
                            "input": {
                                "type": "string",
                                "description": "Task or question for the agent",
                            },
                        },
                        "required": ["agent_dir", "input"],
                    },
                },
            })

        return schema

    def _run_tool_calling_cycle(
        self,
        input_text: str,
        system_prompt: str | None,
        history: list[dict],
    ) -> tuple[str, list[dict], list[dict]]:
        """
        Tool calling cycle with loop guard.

        Iterates up to max_tool_cycles rounds. Each round:
          1. Inference with available tools
          2. If model requests tools → execute → inject results → next round
          3. If model responds directly → return

        Loop guard: stops if the same (tool, args_hash) repeats in a round.

        Returns (output_text, tool_results_log, messages) — the third element
        is the full accumulated message history (including every tool call
        and tool result from this cycle), not just history + a collapsed
        text summary. A caller that needs to continue the conversation (e.g.
        a must-compliance correction retry) should chain from THIS, not from
        the original `history` plus the returned text — otherwise the model
        loses access to file contents it already read and, needing to re-read
        them, may not bother and just re-describe them as text again instead
        of calling write_file. Octopus multi-provider investigation,
        2026-07-20 (FORGE F5 regression) — confirmed independently by two
        probes as a real, code-verified cause of wasted/lost context on retry.
        """
        provider = self._get_provider()
        tools_schema = self._build_tools_schema()
        max_cycles = self.runtime_config.max_tool_cycles
        tool_results_log: list[dict] = []

        messages = list(history)
        messages.append({"role": "user", "content": input_text})

        # Sliding window of recent (call, result) pairs — abort only when the last
        # STUCK_WINDOW entries are all identical, INCLUDING the result. Comparing the
        # result (not just tool+args) lets legitimate polling of an async job survive:
        # e.g. heygen_get_agent_session repeated with the same session_id is expected,
        # but its result changes as the job progresses (status, messages, video_id).
        # A true stuck loop (same call, same unchanged result) is still caught.
        _STUCK_WINDOW = 5
        recent_calls: list[str] = []

        # Tracks how many times we redirected the model back to tool use.
        # Mirrors the native runner's MAX_REFLECTION pushback behaviour.
        _MAX_TOOL_REDIRECTS = 2
        no_tool_redirects = 0

        # Tracks how many times we redirected the model out of a stuck
        # reasoning loop (provider-level loop_detected — see llamacpp.py).
        # Separate counter and separate (stronger) message from
        # no_tool_redirects above: this fires even when tools HAVE already
        # been called earlier in the cycle (tool_results_log non-empty),
        # which is exactly the case no_tool_redirects doesn't cover — the
        # gap that let the RTX 5060 Ti Bonsai run ramble 30K+ tokens with
        # no new tool_call after its first successful write_file (2026-07-18).
        _MAX_LOOP_REDIRECTS = 1
        loop_redirects = 0

        for cycle in range(max_cycles):
            request = ProviderRequest(
                agent_id=self.runtime_config.agent_id,
                input_text="" if cycle > 0 else input_text,
                system_prompt=system_prompt,
                model=self.runtime_config.model_default,
                history=messages[:-1] if cycle == 0 else messages,
                tools_schema=tools_schema if tools_schema else None,
            )
            response = provider.generate(request)

            if response.metadata.get("loop_detected") and loop_redirects < _MAX_LOOP_REDIRECTS:
                loop_redirects += 1
                self.logger.warning(
                    "loop_detected[%d/%d]: model stuck after %s tokens (no action committed, "
                    "or repeated content) — redirecting",
                    loop_redirects, _MAX_LOOP_REDIRECTS,
                    response.metadata.get("decoded_tokens_approx"),
                )
                messages.append({"role": "assistant", "content": response.output_text})
                messages.append({
                    "role": "user",
                    "content": (
                        "You have been reasoning for a long time without taking any action "
                        "or giving a final answer. Stop explaining your plan. In your next "
                        "message, either call a tool immediately, or — if the task is already "
                        "done — give your final answer in one short paragraph."
                    ),
                })
                continue

            if not response.tool_calls:
                # If tools are available and none have been executed yet, push back
                # exactly like the native runner does with REFLECTION_PROMPT.
                if (
                    tools_schema
                    and not tool_results_log
                    and no_tool_redirects < _MAX_TOOL_REDIRECTS
                ):
                    no_tool_redirects += 1
                    self.logger.info(
                        "no_tool_redirect[%d/%d]: model responded without tools — redirecting",
                        no_tool_redirects, _MAX_TOOL_REDIRECTS,
                    )
                    messages.append({"role": "assistant", "content": response.output_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            "You have not used any tools yet. "
                            "Do NOT output code or text directly — use the available tools to complete the task. "
                            "Call the appropriate tool now to proceed."
                        ),
                    })
                    continue

                # The redirect above only fires while zero tools have EVER been
                # called (tool_results_log empty) — the instant the model calls
                # even one read_file, this gate goes permanently silent for the
                # rest of the cycle, per that condition. That's the exact gap
                # that let FORGE F5 through unfixed: the model reads several
                # source files (tool_results_log non-empty), writes a full,
                # correct-looking analysis as chat TEXT instead of via
                # write_file, and returns here — with nothing left to catch it,
                # since must_compliance only runs afterward in run(), by which
                # point this cycle has already ended. Octopus multi-provider
                # investigation, 2026-07-20 — confirmed: the model completed
                # every attempt via exactly this path, never the loop_guard or
                # the max_cycles/final-inference fallback below. Reuse the same
                # filename-existence check must_compliance uses in run(), but
                # here — before the cycle ends — so a still-missing required
                # file can trigger one real push toward calling the write tool
                # while tool context is still fresh. Separate, tighter budget
                # (own counter, checked here) so a model that truly has nothing
                # left to write can't be redirected forever.
                if (
                    tools_schema
                    and tool_results_log
                    and no_tool_redirects < _MAX_TOOL_REDIRECTS
                ):
                    missing_files = self._missing_must_files()
                    if missing_files:
                        no_tool_redirects += 1
                        self.logger.info(
                            "no_tool_redirect[%d/%d]: required file(s) not yet written (%s) — redirecting",
                            no_tool_redirects, _MAX_TOOL_REDIRECTS, ", ".join(missing_files),
                        )
                        messages.append({"role": "assistant", "content": response.output_text})
                        messages.append({
                            "role": "user",
                            "content": (
                                "You have described the content above but have not actually "
                                "saved it. The following required file(s) still do not exist "
                                f"on disk: {', '.join(missing_files)}. Call the write_file tool "
                                "now for each of them, with the full content you just described. "
                                "Do not just repeat it as chat text."
                            ),
                        })
                        continue

                messages.append({"role": "assistant", "content": response.output_text})
                return response.output_text, tool_results_log, messages

            # Always append the assistant turn that requested tool_calls, even when
            # output_text is empty.  Without this, cycles > 0 send [user, tool(result)]
            # to Ollama with no preceding assistant message — which is invalid and causes
            # qwen3.5 to return empty responses (OllamaResponseError in production).
            messages.append({
                "role": "assistant",
                "content": response.output_text or "",
                "tool_calls": [
                    {"function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in response.tool_calls
                ],
            })

            loop_detected = False
            for tc in response.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("arguments") or {}
                call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"

                self.logger.info("tool_call[%d]: %s args=%s", cycle, tool_name, tool_args)
                result = self._execute_tool(tool_name, **tool_args)
                tool_results_log.append({
                    "tool": tool_name, "args": tool_args,
                    "result": result, "cycle": cycle,
                })
                result_text = json.dumps(result, ensure_ascii=False, default=str) if result else "null"
                messages.append({"role": "tool", "content": result_text, "name": tool_name})

                # Compare call + result so legitimate polling (same call, evolving
                # result) doesn't trip the guard — only a truly stuck loop (same call,
                # same unchanged result) does.
                call_result_key = f"{call_key}::{result_text}"
                recent_calls.append(call_result_key)
                if len(recent_calls) > _STUCK_WINDOW:
                    recent_calls.pop(0)

                if (
                    len(recent_calls) == _STUCK_WINDOW
                    and len(set(recent_calls)) == 1
                ):
                    self.logger.warning(
                        "loop_guard: tool '%s' called %d consecutive times with unchanged result — aborting",
                        tool_name, _STUCK_WINDOW,
                    )
                    loop_detected = True
                    break

            if loop_detected:
                break

        # Ciclos esgotados ou loop detectado — última inferência sem tools.
        self.logger.warning("tool_cycle: max_cycles=%d reached or loop detected — final inference", max_cycles)

        # Injeta lembrete de conclusão com resumo do que foi executado,
        # para que o modelo produza uma resposta final baseada em evidências reais.
        must_rules = self.agent_spec.guardrails.must
        import re as _re

        # Resumo das ferramentas executadas
        if tool_results_log:
            exec_lines = []
            for entry in tool_results_log:
                args_preview = json.dumps(entry.get("args", {}), ensure_ascii=False)[:80]
                exec_lines.append(f"  - {entry['tool']}({args_preview})")
            exec_summary = "Tools already executed:\n" + "\n".join(exec_lines)
        else:
            exec_summary = "No tools were executed."

        completion_hint = (
            f"Produce your final response based on the tools executed above.\n\n"
            f"{exec_summary}"
        )
        if must_rules:
            phrases = []
            for rule in must_rules:
                quoted = _re.findall(r"'([^']+)'", rule)
                phrases.extend(quoted)
            if phrases:
                completion_hint += "\n\nYour response MUST include: " + ", ".join(f"'{p}'" for p in phrases[:3])

        messages.append({"role": "user", "content": completion_hint})

        # tools_schema was omitted here originally — meaning the model was
        # physically unable to call write_file (or any tool) at exactly the
        # moment it's told to "produce your final response based on the
        # tools executed above", even if the honest final response requires
        # persisting something it only described in text so far. Octopus
        # multi-provider investigation, 2026-07-20 (FORGE F5 regression):
        # code-verified by two independent probes (qwen). Give it one more
        # real chance to call a tool here — if it does, run the tool(s) and
        # take the text response that follows; if it doesn't, this behaves
        # exactly as before (a plain completion).
        final_req = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text="",
            system_prompt=system_prompt,
            model=self.runtime_config.model_default,
            history=messages,
            tools_schema=tools_schema if tools_schema else None,
        )
        final_response = provider.generate(final_req)
        if final_response.tool_calls:
            messages.append({
                "role": "assistant",
                "content": final_response.output_text,
                "tool_calls": final_response.tool_calls,
            })
            for tc in final_response.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("arguments") or {}
                self.logger.info("tool_call[final]: %s args=%s", tool_name, tool_args)
                result = self._execute_tool(tool_name, **tool_args)
                tool_results_log.append({
                    "tool": tool_name, "args": tool_args,
                    "result": result, "cycle": "final",
                })
                result_text = json.dumps(result, ensure_ascii=False, default=str) if result else "null"
                messages.append({"role": "tool", "content": result_text, "name": tool_name})
            closing_req = ProviderRequest(
                agent_id=self.runtime_config.agent_id,
                input_text="",
                system_prompt=system_prompt,
                model=self.runtime_config.model_default,
                history=messages,
            )
            final_response = provider.generate(closing_req)
        return final_response.output_text, tool_results_log, messages

    @staticmethod
    def _strip_xml_tool_tags(text: str) -> str:
        """Removes <tool_use>...</tool_use> blocks that leak in qwen3.5:27b output."""
        import re
        cleaned = re.sub(r"<tool_use>.*?</tool_use>", "", text, flags=re.DOTALL)
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    def _judge_model(self) -> str:
        """
        Model used for must_compliance/guardrail LLM-judge calls — deliberately
        NOT self.runtime_config.model_default (the candidate under test) unless
        no override is set. Letting a candidate judge its own output means any
        instability it has (e.g. a reasoning-loop tendency) contaminates the
        judgment too: confirmed 2026-07-21, gemma4:12b's must_compliance judge
        call itself fell into a 500+ line repetitive loop ("Wait, let me check
        again...") that filled the context window and stalled the server —
        the exact same failure mode the candidate was being tested for,
        reproduced inside the harness's own verification step. Set
        AGENTFORGE_JUDGE_MODEL to pin a stable judge (e.g. the production
        champion) across every benchmark run regardless of which candidate is
        under test; falls back to model_default only if unset, so existing
        single-model setups are unaffected.
        """
        return os.environ.get("AGENTFORGE_JUDGE_MODEL", self.runtime_config.model_default)

    def _missing_must_files(self) -> list[str]:
        """
        Filename-shaped quoted terms from guardrails.must that don't exist on
        disk yet. Cheap, deterministic subset of _check_must_compliance's
        filename check — used mid-cycle (inside _run_tool_calling_cycle,
        before the model is allowed to finish without calling write_file),
        not just after the fact in run().
        """
        import re
        import os as _os

        must_rules = self.agent_spec.guardrails.must
        if not must_rules:
            return []

        workdir = Path(_os.environ.get("AGENT_WORKDIR", "."))
        _filename_re = re.compile(r"^[\w.-]+\.[A-Za-z0-9]{1,5}$")

        missing_files: list[str] = []
        for rule in must_rules:
            quoted = re.findall(r"'([^']+)'", rule)
            filename_terms = [q for q in quoted if _filename_re.match(q)]
            for q in filename_terms:
                if not (workdir / q).exists() and q not in missing_files:
                    missing_files.append(q)
        return missing_files

    def _check_must_compliance(
        self,
        output_text: str,
        tool_results_log: list[dict] | None = None,
    ) -> list[str]:
        """
        Checks which 'must' rules were NOT met.

        For quoted-phrase rules: checks output_text first, then tool execution
        evidence (a rule is satisfied if the quoted phrase appears in any tool
        result or if a matching tool was called).
        For open rules: LLM judge receives both the output text and a summary
        of all tools executed, so it can reason from real evidence.
        """
        must_rules = self.agent_spec.guardrails.must
        if not must_rules:
            return []

        import re
        tool_results_log = tool_results_log or []

        # Build flat evidence string from tool execution log.
        # Truncate per-entry args to 200 chars so that long write_file content
        # doesn't push later entries (like run_bash) out of the judge's window.
        evidence_parts = []
        evidence_parts_full = []
        for entry in tool_results_log:
            args_str = json.dumps(entry.get("args", {}), ensure_ascii=False)
            result_str = json.dumps(entry.get("result", ""), ensure_ascii=False)
            evidence_parts.append(
                f"tool={entry['tool']} args={args_str[:200]} result={result_str[:200]}"
            )
            evidence_parts_full.append(
                f"tool={entry['tool']} args={args_str} result={result_str}"
            )
        evidence_text = "\n".join(evidence_parts) if evidence_parts else "(no tools executed)"
        # Untruncated evidence — only for the deterministic quoted-phrase check below.
        # The 200-char truncation exists to keep the LLM judge's context window from
        # being crowded out by one big write_file entry (Bug 10); a plain substring
        # search has no such concern and needs the full content, otherwise a rule
        # satisfied deep inside a large write_file (e.g. a later section heading)
        # is wrongly reported as missing — confirmed 2026-07-18 (Bonsai F3 crash).
        evidence_text_full = (
            "\n".join(evidence_parts_full) if evidence_parts_full else "(no tools executed)"
        )

        # Called tool names for quick lookup
        called_tools = {e["tool"] for e in tool_results_log}

        missing = []
        open_rules = []

        import os as _os
        workdir = Path(_os.environ.get("AGENT_WORKDIR", "."))
        _filename_re = re.compile(r"^[\w.-]+\.[A-Za-z0-9]{1,5}$")

        for rule in must_rules:
            # Rules with quoted phrases → deterministic check against output + evidence
            quoted = re.findall(r"'([^']+)'", rule)
            if quoted:
                filename_terms = [q for q in quoted if _filename_re.match(q)]
                if filename_terms:
                    # Filename-shaped quoted term(s) present → authoritative and
                    # mandatory (AND), not one-of-many alongside other quoted
                    # words in the same rule. A rule like "criar 'x.json' com
                    # campo 'status' preenchido" must not pass just because
                    # 'status' happens to appear in the prose while x.json was
                    # never written — confirmed 2026-07-20 (REAL P2): exactly
                    # this shape ('agents_report.md' ... 'error') was marked
                    # satisfied by the word 'error' alone. Only a real file on
                    # disk counts for the filename term(s); other quoted words
                    # in the same rule are ignored for this determination.
                    satisfied = all((workdir / q).exists() for q in filename_terms)
                else:
                    satisfied = any(
                        q.lower() in output_text.lower() or q.lower() in evidence_text_full.lower()
                        for q in quoted
                    )
                if not satisfied:
                    missing.append(rule)
            elif any(
                re.search(rf"\b{re.escape(tool_name)}\b", rule) for tool_name in called_tools
            ):
                # Rule mentions the name of a tool that was genuinely called
                # (per tool_results_log) → satisfied deterministically, skip
                # the LLM judge entirely for this rule. Confirmed 2026-07-21
                # (media-generator agent): the judge false-negatived "chamar
                # a tool comfyui_generate_image de verdade" even with the
                # call clearly present in evidence, causing the agent to
                # redo the (expensive, real) image generation 2-3x per
                # request. Only fires when the tool WAS called — a rule
                # whose tool was never called still goes to the judge below,
                # since whether it was actually required needs judgment.
                continue
            else:
                open_rules.append(rule)

        # Open rules → LLM judge with full evidence context
        if open_rules:
            rules_text = "\n".join(f"- {r}" for r in open_rules)
            prompt = (
                "Determine which of the following MANDATORY rules were NOT met.\n"
                "Consider BOTH the final response text AND the tool execution evidence.\n"
                "A rule about executing a tool is satisfied if that tool appears in the evidence.\n"
                "Respond ONLY with the unmet rules, one per line.\n"
                "If all were met, respond exactly: NONE\n\n"
                f"Mandatory rules:\n{rules_text}\n\n"
                f"Tool execution evidence:\n{evidence_text[:3000]}\n\n"
                f"Final response text:\n{output_text[:2000]}"
            )
            provider = self._get_provider()
            req = ProviderRequest(
                agent_id=self.runtime_config.agent_id,
                input_text=prompt,
                system_prompt=None,
                model=self._judge_model(),
                history=[],
            )
            resp = provider.generate(req)
            result = resp.output_text.strip()
            if result and result.upper() != "NONE":
                missing += [line.lstrip("- ").strip() for line in result.splitlines() if line.strip()]

        return missing

    def _check_guardrail_violations(self, output_text: str) -> list[str]:
        """Uses the model to detect which must_not rules were violated in the output."""
        must_not = self.agent_spec.guardrails.must_not
        if not must_not:
            return []

        rules = "\n".join(f"- {r}" for r in must_not)
        prompt = (
            "Analyze the text below and identify WHICH of the following rules were violated.\n"
            "Respond ONLY with the violated rules, one per line.\n"
            "If none were violated, respond exactly: NONE\n\n"
            f"Prohibited rules:\n{rules}\n\n"
            f"Text to analyze:\n{output_text}"
        )
        provider = self._get_provider()
        req = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text=prompt,
            system_prompt=None,
            model=self._judge_model(),
            history=[],
        )
        resp = provider.generate(req)
        result = resp.output_text.strip()
        if not result or result.upper() == "NONE":
            return []
        return [line.lstrip("- ").strip() for line in result.splitlines() if line.strip()]

    def _apply_guardrails(
        self,
        input_text: str,
        output_text: str,
        system_prompt: str | None,
        history: list[dict],
        tool_results_log: list[dict] | None = None,
        max_retries: int = 2,
    ) -> tuple[str, list[str]]:
        """
        Checks must_not and re-executes with a correction prompt up to max_retries times.

        If the agent's actual deliverable was persisted via a write_file tool call,
        the violation check and correction run against that FILE CONTENT instead of
        the chat-level output_text — and the corrected text is re-written to disk via
        write_file. Without this, a write_file-based agent (e.g. linkedin-writer)
        never re-emits the file after correction: the engine would "fix" only the
        in-memory response while the file on disk keeps the original violation.

        Returns (final_output_text, remaining_violations).
        """
        last_write = None
        if tool_results_log:
            for entry in reversed(tool_results_log):
                if entry.get("tool") == "write_file":
                    last_write = entry
                    break

        content_to_check = last_write["args"].get("content") if last_write else output_text
        violations = self._check_guardrail_violations(content_to_check)
        if not violations:
            return output_text, []

        provider = self._get_provider()
        corrected = content_to_check
        for attempt in range(max_retries):
            self.logger.warning(
                "guardrail[%d/%d]: violations detected: %s",
                attempt + 1, max_retries, violations,
            )
            correction_prompt = (
                "Your previous response violated the following restrictions:\n"
                + "\n".join(f"- {v}" for v in violations)
                + "\n\nRewrite your response without violating these restrictions.\n\n"
                f"Original question: {input_text}\n\n"
                f"Content to rewrite:\n{corrected}"
            )
            req = ProviderRequest(
                agent_id=self.runtime_config.agent_id,
                input_text=correction_prompt,
                system_prompt=system_prompt,
                model=self.runtime_config.model_default,
                history=history,
            )
            resp = provider.generate(req)
            corrected = resp.output_text
            violations = self._check_guardrail_violations(corrected)
            if not violations:
                break

        if last_write:
            write_path = last_write["args"].get("path")
            result = self._execute_tool("write_file", path=write_path, content=corrected)
            tool_results_log.append({
                "tool": "write_file",
                "args": {"path": write_path, "content": corrected},
                "result": result,
                "cycle": "guardrail_correction",
            })
            self.logger.info("guardrail: re-wrote %s with corrected content", write_path)
            return output_text, violations

        return corrected, violations

    def _reflect(
        self,
        original_input: str,
        output_text: str,
        system_prompt: str | None,
        history: list[dict],
        rounds: int,
    ) -> str:
        """
        Iterative self-criticism: the model reviews its own output N times.
        Returns the refined output after all rounds.
        """
        provider = self._get_provider()
        current = output_text

        for r in range(rounds):
            reflect_prompt = (
                "Review your previous response considering:\n"
                "1. Is it complete and accurate relative to the original question?\n"
                "2. Does it respect all role restrictions?\n"
                "3. Can it be more objective or useful?\n\n"
                "If it is appropriate, respond the same. If not, improve it.\n\n"
                f"Original question: {original_input}\n\n"
                f"Your previous response:\n{current}"
            )
            req = ProviderRequest(
                agent_id=self.runtime_config.agent_id,
                input_text=reflect_prompt,
                system_prompt=system_prompt,
                model=self.runtime_config.model_default,
                history=history,
            )
            resp = provider.generate(req)
            self.logger.info("reflection[%d]: %d → %d chars", r, len(current), len(resp.output_text))
            current = resp.output_text

        return current

    def _build_input_with_tool_results(self, input_text: str, tool_data: dict) -> str:
        tool_json = json.dumps(tool_data, indent=2, default=str)
        return f"{_TOOL_PREVIEW_PREFIX}{tool_json}\n</tool_results>\n\nUser: {input_text}"

    def _build_input_with_tool_results_with_name(
        self, input_text: str, tool_data: dict, tool_name: str = ""
    ) -> str:
        tool_data = _maybe_compress_tool_output(tool_data, tool_name)

        if "_text" in tool_data:
            tool_content = tool_data["_text"]
        else:
            tool_json = json.dumps(tool_data, indent=2, default=str)
            tool_content = tool_content = tool_json

        return f"{_TOOL_PREVIEW_PREFIX}{tool_content}\n</tool_results>\n\nUser: {input_text}"

    @property
    def history(self) -> list[dict[str, str]]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history = []
        from agentforge.runtime.memory import clear_history
        clear_history(self.root_dir)

    def _detect_log_intent(self, input_text: str) -> bool:
        log_keywords = [
            "log",
            "syslog",
            "last lines",
            "last lines of",
            "recent errors",
            "recent events",
            "events",
            "view log",
            "check log",
        ]
        lower_input = input_text.lower()
        return any(kw in lower_input for kw in log_keywords)

    def _detect_file_intent(self, input_text: str) -> bool:
        keywords = [
            "analise",
            "analisar",
            "content",
            "extract",
            "extract",
            "what is the content",
            "explain to me",
            "describe",
            "describe",
            "what is",
            "explain",
        ]
        lower = input_text.lower()
        return any(kw in lower for kw in keywords)

    def _extract_filename_intent(self, input_text: str) -> str | None:
        import re
        text = input_text
        
        m = re.search(r"([A-Z][a-zA-Z]+/[A-Za-z]+/[^\s]+\.(?:pdf|docx?|odt|pptx?))", text)
        if m:
            return m.group(1)
        
        m = re.search(r"([A-Z][a-zA-Z]+/[^\s]+\.(?:pdf|docx?|odt|pptx?))", text)
        if m:
            return m.group(1)
        
        m = re.search(r"([^\s]+\.(?:pdf|docx?|odt|pptx?))", text)
        if m:
            candidate = m.group(1)
            if len(candidate) > 10:
                return candidate
        return None

    def _detect_log_path(self, input_text: str) -> str:
        lower = input_text.lower()
        if "syslog" in lower:
            return "/var/log/syslog"
        if "kern" in lower:
            return "/var/log/kern.log"
        if "messages" in lower:
            return "/var/log/messages"
        return "/var/log/syslog"

    def _log_run(self, result: dict, latency_ms: float) -> None:
        runs_dir = self.root_dir / "runs"
        runs_dir.mkdir(exist_ok=True)
        entry = {
            "agent_id": result["agent_id"],
            "provider": result["provider"],
            "model": result["provider_response"]["model"],
            "input": result["input"][:500],
            "output": result["output"][:500],
            "timestamp": result["metadata"]["timestamp"],
            "latency_ms": round(latency_ms),
        }
        with open(runs_dir / "runs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _inject_rules_to_input(self, input_text: str) -> str:
        """Appends mandatory guardrails to user input for better grounding."""
        must_rules = self.agent_spec.guardrails.must
        if not must_rules:
            return input_text
        
        rules_block = "\n\n### MANDATORY RULES FOR THIS TASK:\n"
        for rule in must_rules:
            rules_block += f"- {rule}\n"
        
        return input_text + rules_block

    def run(self, input_text: str, *, metadata: dict | None = None) -> dict:
        provider = self._get_provider()
        _t0 = time.perf_counter()

        tool_data = None
        # Injeta regras no prompt de usuário para paridade com REAL framework
        final_input = self._inject_rules_to_input(input_text)

        required_tool = next((t for t in self.tools if t.required), None)
        if required_tool:
            tool_data = self._execute_tool(required_tool.name)
            if tool_data:
                if self.runtime_config.agent_id == "vault-pilot":
                    final_input = self._build_input_with_tool_results_with_name(
                        input_text, tool_data, tool_name=required_tool.name
                    )
                else:
                    final_input = self._build_input_with_tool_results(input_text, tool_data)

        if self._detect_log_intent(input_text):
            log_tool = next((t for t in self.tools if t.name == "read_log_tail"), None)
            if log_tool:
                log_path = self._detect_log_path(input_text)
                log_data = execute_tool(log_tool.name, log_path=log_path)
                if log_data:
                    log_json = json.dumps(log_data, indent=2, default=str)
                    final_input = f"{final_input}\n\n<log_results>\n{log_json}\n</log_results>"

        if self._detect_file_intent(input_text):
            extract_tool = next((t for t in self.tools if t.name == "extract_file_content"), None)
            if extract_tool:
                filename = self._extract_filename_intent(input_text)
                if filename:
                    if not filename.startswith("/"):
                        filename = f"/home/conrado/testes/vault/input/{filename}"
                    file_data = execute_tool(extract_tool.name, file_path=filename)
                    if file_data and not file_data.get("error"):
                        file_json = json.dumps(file_data, indent=2, default=str)
                        final_input = f"{final_input}\n\n<file_content>\n{file_json}\n</file_content>"

        history = list(self._history) if self.runtime_config.conversation_multi_turn else []
        system_prompt = self._read_system_prompt()

        self.logger.info(
            "run: agent=%s provider=%s model=%s mode=%s turn=%d input=%r",
            self.runtime_config.agent_id,
            self.runtime_config.provider,
            self.runtime_config.model_default,
            self.runtime_config.workflow_mode,
            len(history) // 2 + 1,
            input_text,
        )

        tool_results_log: list[dict] = []
        cycle_messages: list[dict] = []

        if self.runtime_config.workflow_mode == "respond_or_tool":
            output_text, tool_results_log, cycle_messages = self._run_tool_calling_cycle(
                final_input, system_prompt, history
            )
            raw_response = None
        else:
            request = ProviderRequest(
                agent_id=self.runtime_config.agent_id,
                input_text=final_input,
                system_prompt=system_prompt,
                model=self.runtime_config.model_default,
                history=history,
            )
            response = provider.generate(request)
            output_text = response.output_text
            raw_response = response.raw_response
            if not self.runtime_config.conversation_multi_turn and raw_response and "context" in raw_response:
                raw_response = {k: v for k, v in raw_response.items() if k != "context"}

        # Reflexão autônoma — refina o output N vezes antes de retornar.
        reflection_rounds = self.runtime_config.reflection_rounds
        if reflection_rounds > 0:
            output_text = self._reflect(
                input_text, output_text, system_prompt, history, reflection_rounds
            )

        # Remove XML tool_use tags que vazam no output do qwen3.5:27b.
        output_text = self._strip_xml_tool_tags(output_text)

        # Guardrails ativos — verifica must_not e retenta se necessário.
        guardrail_violations: list[str] = []
        if self.agent_spec.guardrails.must_not:
            output_text, guardrail_violations = self._apply_guardrails(
                input_text, output_text, system_prompt, history, tool_results_log
            )
            if guardrail_violations:
                self.logger.error(
                    "guardrail: persistent violations after retries: %s", guardrail_violations
                )

        # Must compliance — verifica regras obrigatórias e corrige se necessário.
        #
        # Loops up to _MAX_MUST_COMPLIANCE_RETRIES times, re-checking after
        # each correction, instead of a single shot-and-accept attempt. The
        # native forge_runner.py runner (pre-AgentForge) does this natively —
        # MAX_REFLECTION=3 rounds, each re-prompting the model to compare its
        # own work against the task point by point before declaring done —
        # and reliably gets 100% on tasks this single-shot version stalled on
        # at ~18% (confirmed 2026-07-20, FORGE F5: model said it was done,
        # and even said the required completion phrase, after just one
        # generic nudge, without ever having called write_file for any of
        # the 3 required documents — one correction attempt wasn't enough
        # for a model that confidently considers a text description
        # equivalent to having saved the file).
        _MAX_MUST_COMPLIANCE_RETRIES = 3
        if self.agent_spec.guardrails.must:
            import re as _re
            _filename_re = _re.compile(r"^[\w.-]+\.[A-Za-z0-9]{1,5}$")

            def _missing_filename(rule: str) -> str | None:
                for q in _re.findall(r"'([^']+)'", rule):
                    if _filename_re.match(q):
                        return q
                return None

            for _attempt in range(_MAX_MUST_COMPLIANCE_RETRIES):
                must_missing = self._check_must_compliance(output_text, tool_results_log)
                if not must_missing:
                    break
                self.logger.warning(
                    "must_compliance[%d/%d]: rules not met: %s",
                    _attempt + 1, _MAX_MUST_COMPLIANCE_RETRIES, must_missing,
                )
                # Rules with quoted phrases are USUALLY textual/formatting
                # requirements (section headers, exact phrases, language) that
                # never need a new tool call — inviting tool use for those
                # risks an unbounded tool-calling spiral (Bug 13 — confirmed
                # 2026-07-15 Qwythos, escalated to a full context-window crash
                # 2026-07-18 Bonsai F3). But a quoted term can also be a
                # filename (see _check_must_compliance's file-existence check
                # above) — for those, "add the missing text to your response"
                # is actively wrong: the model needs to call write_file, not
                # talk about the file.
                missing_files = [f for r in must_missing if (f := _missing_filename(r))]
                all_textual = not missing_files and all(
                    _re.search(r"'[^']+'", r) for r in must_missing
                )
                if missing_files:
                    files_list = ", ".join(f"'{fn}'" for fn in missing_files)
                    correction = (
                        "Your response is incomplete. The following mandatory rules were not met:\n"
                        + "\n".join(f"- {r}" for r in must_missing)
                        + f"\n\nYou must call the write_file tool now to actually save {files_list} "
                        + "— describing the content in your chat response does not save it to disk. "
                        + "If you already wrote this content in a previous response, call write_file "
                        + "with that same content for each missing file, one call per file."
                    )
                elif all_textual:
                    correction = (
                        "Your response is incomplete. The following mandatory rules were not met:\n"
                        + "\n".join(f"- {r}" for r in must_missing)
                        + "\n\nThese are textual/formatting requirements only (exact phrases, "
                        + "section headers, or language). Add the missing text or formatting to "
                        + "your existing response. Do NOT call any tools."
                    )
                else:
                    correction = (
                        "Your response is incomplete. The following mandatory rules were not met:\n"
                        + "\n".join(f"- {r}" for r in must_missing)
                        + "\n\nComplete your response by including the missing items. Use tools if necessary."
                    )
                # Reinicia um ciclo de ferramentas focado na correção.
                #
                # Chains from cycle_messages (the FULL accumulated history of
                # the previous cycle — every tool call and tool result, not
                # just the collapsed final text) rather than history + a
                # bare assistant-text turn. The latter silently discarded
                # every read_file result from the prior cycle, so the model
                # was told "call write_file now" for content it could no
                # longer see — it would either re-read the same files again
                # (wasted turns) or, worse, just re-describe them as text
                # again since regenerating write_file's exact args without
                # the source in context is unreliable. Falls back to the old
                # collapsed form only if cycle_messages is empty (shouldn't
                # happen once _run_tool_calling_cycle always returns it, kept
                # only as a defensive guard). Octopus multi-provider
                # investigation, 2026-07-20 (FORGE F5 regression).
                retry_history = cycle_messages or (
                    history + [{"role": "assistant", "content": output_text}]
                )
                output_text, correction_tools, cycle_messages = self._run_tool_calling_cycle(
                    correction,
                    system_prompt,
                    retry_history,
                )
                tool_results_log.extend(correction_tools)

                # A correção de must roda um ciclo de ferramentas livre, sem
                # restrição de must_not — pode reintroduzir violações já corrigidas
                # (ex.: emojis) na nova chamada de write_file. Revalida.
                if self.agent_spec.guardrails.must_not:
                    output_text, guardrail_violations = self._apply_guardrails(
                        input_text, output_text, system_prompt, history, tool_results_log
                    )
                    if guardrail_violations:
                        self.logger.error(
                            "guardrail: persistent violations after must_compliance retry: %s",
                            guardrail_violations,
                        )
            else:
                still_missing = self._check_must_compliance(output_text, tool_results_log)
                if still_missing:
                    self.logger.error(
                        "must_compliance: still not met after %d attempts: %s",
                        _MAX_MUST_COMPLIANCE_RETRIES, still_missing,
                    )

        # Update in-memory history for multi-turn sessions.
        if self.runtime_config.conversation_multi_turn:
            self._history.append({"role": "user", "content": input_text})
            self._history.append({"role": "assistant", "content": output_text})
            self._history = apply_window(
                self._history,
                self.runtime_config.memory_max_turns,
                self.runtime_config.memory_policy,
            )
            if self.runtime_config.memory_enabled and self.runtime_config.memory_type != "none":
                save_history(self.root_dir, self._history)

        latency_ms = (time.perf_counter() - _t0) * 1000
        result = {
            "agent_id": self.runtime_config.agent_id,
            "provider": self.runtime_config.provider,
            "input": input_text,
            "output": output_text,
            "metadata": {
                "provider": self.runtime_config.provider,
                "workflow_mode": self.runtime_config.workflow_mode,
                "channel_type": self.runtime_config.channel_type,
                "model_default": self.runtime_config.model_default,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": round(latency_ms),
                "tool_executed": required_tool.name if required_tool else None,
                "tool_data": tool_data,
                "tool_calls_log": tool_results_log if tool_results_log else None,
                "conversation_turn": len(self._history) // 2,
                "guardrail_violations": guardrail_violations if guardrail_violations else None,
                **(metadata or {}),
            },
            "provider_response": {
                "provider": self.runtime_config.provider,
                "model": self.runtime_config.model_default,
                "raw_response": raw_response,
            },
        }
        self._log_run(result, latency_ms)

        if self.runtime_config.memory_feed_mem0:
            from agentforge.runtime.mem0_hook import feed_async  # noqa: PLC0415
            feed_async(
                self.runtime_config.agent_id,
                input_text,
                output_text,
                tool_results_log,
            )

        return result

    def _run_with_tool_data(self, input_text: str, tool_data: dict) -> str:
        """
        Executes a call to the model injecting pre-formatted tool_data,
        without going through automatic intent detection.

        Intended use exclusively for benchmarks and internal tests.
        DO NOT use this method in the production pipeline (normal CLI).
        DO NOT change the behavior of run() or the normal flow.
        """
        if "_text" in tool_data:
            tool_content = tool_data["_text"]
            prompt = f"{_TOOL_PREVIEW_PREFIX}{tool_content}\n</tool_results>\n\nUser: {input_text}"
        else:
            prompt = self._build_input_with_tool_results(input_text, tool_data)

        request = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text=prompt,
            system_prompt=self._read_system_prompt(),
            model=self.runtime_config.model_default,
            history=[],
        )
        provider = self._get_provider()
        response = provider.generate(request)
        return response.output_text

    def _run_with_file_content(
        self,
        input_text: str,
        file_text: str,
        mode: str = "current_tag",
        history: list | None = None,
    ) -> str:
        """
        Executes a call to the model injecting document content
        in different formats, without going through automatic intent detection.

        history:
          - None → empty history (same behavior as V2).
          - list provided → used directly; allows injecting synthetic history
            for context corruption benchmarks.

        Intended use exclusively for benchmarks and internal tests.
        DO NOT use in the production pipeline.
        """
        prompt = _build_input_with_file_content(
            input_text=input_text,
            file_text=file_text,
            mode=mode,
            tool_prefix="",
        )

        request = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text=prompt,
            system_prompt=self._read_system_prompt(),
            model=self.runtime_config.model_default,
            history=history if history is not None else [],
        )
        provider = self._get_provider()
        response = provider.generate(request)
        return response.output_text
