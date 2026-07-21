from __future__ import annotations

import json
import os
import time

import requests

from agentforge.gpu_broker_client import acquire_gpu
from agentforge.providers.base import BaseProvider, ProviderError, ProviderRequest, ProviderResponse

_DEFAULT_HOST = "http://localhost:8082"
_DEFAULT_TIMEOUT = 900
_CONNECT_TIMEOUT = 10  # seconds to establish TCP connection
_CHUNK_TIMEOUT = 60  # seconds of stream inactivity (between SSE chunks) before erroring
# Tokens generated with no content/tool_calls committed yet (still purely inside
# reasoning_content) before we treat it as a stuck "explaining without acting" loop
# and abort the stream early instead of burning the full max_tokens budget.
_DEFAULT_LOOP_GUARD_TOKENS = 6000
# The loop guard above only catches "stuck reasoning, zero content" — it
# requires `not content_parts`. Some model templates (e.g. gemma4's
# `<|channel>thought...<channel|>` tags) aren't recognized by llama.cpp as a
# separate reasoning channel, so their thinking lands in `content` instead of
# `reasoning_content` and slips right past that check. Confirmed 2026-07-21:
# gemma4:12b's must_compliance judge call repeated the same line ("Wait, let
# me check the main function again.") 500+ times as regular content, filled
# the context window, and stalled the server. This second guard catches
# repetition directly regardless of which channel it landed in. Only lines at
# least this long count, to avoid false positives on short, legitimately
# repeated tokens (table separators, bullet markers, etc.).
_DEFAULT_REPETITION_THRESHOLD = 6
_MIN_REPEAT_LINE_LEN = 20


class LlamaCppProviderError(ProviderError):
    pass


class LlamaCppConnectionError(LlamaCppProviderError):
    pass


class LlamaCppResponseError(LlamaCppProviderError):
    pass


def _normalize_messages(messages: list[dict]) -> list[dict]:
    """Convert AgentForge history format to OpenAI-compat format for llama.cpp.

    AgentForge stores tool_calls as:
      {"function": {"name": "...", "arguments": {...}}}  (no type, no id, args as dict)

    llama.cpp requires:
      {"id": "call_0", "type": "function", "function": {"name": "...", "arguments": "..."}}
      and tool result messages need "tool_call_id" matching the id.
    """
    result: list[dict] = []
    call_id_counter = 0
    # Maps (position_in_result, call_index) → id, so we can back-fill tool results.
    pending_ids: list[str] = []

    for msg in messages:
        role = msg.get("role", "")

        if role == "assistant" and msg.get("tool_calls"):
            raw_tcs = msg["tool_calls"]
            pending_ids = []
            normalized_tcs = []
            for tc in raw_tcs:
                call_id = f"call_{call_id_counter}"
                call_id_counter += 1
                pending_ids.append(call_id)
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, dict):
                    args_str = json.dumps(args, ensure_ascii=False)
                else:
                    args_str = args
                normalized_tcs.append({
                    "id": call_id,
                    "type": "function",
                    "function": {"name": fn.get("name", ""), "arguments": args_str},
                })
            result.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": normalized_tcs,
            })

        elif role == "tool":
            # Match this result to the next pending_id in order.
            call_id = pending_ids.pop(0) if pending_ids else f"call_{call_id_counter}"
            result.append({
                "role": "tool",
                "content": msg.get("content", ""),
                "tool_call_id": call_id,
            })

        else:
            result.append(msg)

    return result


class LlamaCppProvider(BaseProvider):
    name = "llamacpp"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        messages: list[dict] = []

        system = request.system_prompt or ""
        messages.append({"role": "system", "content": system})

        # Normalize history: convert AgentForge Ollama-style tool_calls to
        # the OpenAI-compat format expected by llama.cpp.
        for msg in _normalize_messages(request.history):
            messages.append(msg)

        if request.input_text:
            messages.append({"role": "user", "content": request.input_text})

        # LLAMACPP_THINKING_BUDGET=0 (default): disable Qwen3 thinking entirely.
        # LLAMACPP_THINKING_BUDGET=N (N>0): allow up to N thinking tokens before response.
        # /no_think in user messages does NOT work on llama.cpp — use chat_template_kwargs.
        thinking_budget = int(os.environ.get("LLAMACPP_THINKING_BUDGET", "0"))

        payload: dict = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "temperature": 0,
        }
        if thinking_budget > 0:
            payload["chat_template_kwargs"] = {"enable_thinking": True}
            payload["max_tokens"] = thinking_budget + 8192
        else:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
            payload["max_tokens"] = 8192
        if request.tools_schema:
            payload["tools"] = request.tools_schema

        base_url = os.environ.get("LLAMACPP_HOST", _DEFAULT_HOST).rstrip("/")
        # Real wall-clock deadline for the whole call. Not to be confused with
        # requests' own (connect, read) timeout below, which only bounds
        # inactivity BETWEEN chunks — with streaming that's tight (_CHUNK_TIMEOUT),
        # but a model that keeps producing chunks steadily for hours would never
        # trip it. total_timeout is checked explicitly per chunk instead.
        total_timeout = int(os.environ.get("LLAMACPP_TIMEOUT", str(_DEFAULT_TIMEOUT)))
        loop_guard_tokens = int(
            os.environ.get("LLAMACPP_LOOP_GUARD_TOKENS", str(_DEFAULT_LOOP_GUARD_TOKENS))
        )
        repetition_threshold = int(
            os.environ.get("LLAMACPP_REPETITION_THRESHOLD", str(_DEFAULT_REPETITION_THRESHOLD))
        )

        reasoning_parts: list[str] = []
        content_parts: list[str] = []
        tool_call_chunks: dict[int, dict] = {}
        finish_reason: str | None = None
        decoded_tokens_approx = 0
        loop_detected = False
        line_repeat_counts: dict[str, int] = {}
        content_deltas_since_repeat_check = 0

        try:
            with acquire_gpu(client=f"agentforge:{request.agent_id}", priority="batch", max_wait_s=total_timeout):
                # Started AFTER the broker hand-off, not before — total_timeout must
                # bound the LLM call itself, not GPU queueing (which has its own
                # max_wait_s budget above). Starting the clock too early caused a
                # real false-positive: a broker queue wait alone could burn most of
                # the budget, leaving the actual generation instantly "timed out".
                start = time.monotonic()
                with requests.post(
                    f"{base_url}/v1/chat/completions",
                    json=payload,
                    stream=True,
                    timeout=(_CONNECT_TIMEOUT, _CHUNK_TIMEOUT),
                ) as resp:
                    if resp.status_code != 200:
                        raise LlamaCppResponseError(
                            f"llama.cpp returned status {resp.status_code}: {resp.text[:300]}"
                        )
                    # decode_unicode=True lets requests guess the response
                    # encoding from headers, and llama.cpp's SSE stream doesn't
                    # declare charset=utf-8 — requests silently falls back to
                    # Latin-1 for text/* without one, mojibaking any accented
                    # PT-BR content (confirmed 2026-07-20: corrupted must_compliance
                    # feedback strings, sent the model into a confused reasoning
                    # loop over a phrase it had actually already produced correctly).
                    # llama.cpp's API is JSON/SSE — always UTF-8 — so decode
                    # explicitly instead of trusting the guess.
                    for raw_line in resp.iter_lines(decode_unicode=False):
                        line = raw_line.decode("utf-8")
                        if time.monotonic() - start > total_timeout:
                            resp.close()
                            raise LlamaCppConnectionError(
                                f"Total timeout ({total_timeout}s) exceeded waiting for "
                                f"llama.cpp ({base_url}) to finish generating."
                            )
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[len("data:"):].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        choice = (chunk.get("choices") or [{}])[0]
                        delta = choice.get("delta", {})
                        fr = choice.get("finish_reason")
                        if fr:
                            finish_reason = fr

                        rc = delta.get("reasoning_content")
                        if rc:
                            reasoning_parts.append(rc)
                            decoded_tokens_approx += 1
                        ct = delta.get("content")
                        if ct:
                            content_parts.append(ct)
                            decoded_tokens_approx += 1
                            content_deltas_since_repeat_check += 1

                        # Repetition guard: re-derive line counts from the tail of the
                        # accumulated content periodically (not every delta — most SSE
                        # chunks are a few characters, so lines only actually complete
                        # every so often; checking in batches keeps this cheap). Only
                        # lines long enough to be meaningful count, so short repeated
                        # tokens (bullets, table dividers) can't trip it.
                        if content_deltas_since_repeat_check >= 20 and not tool_call_chunks:
                            content_deltas_since_repeat_check = 0
                            tail = "".join(content_parts)[-8000:]
                            line_repeat_counts = {}
                            for raw_ln in tail.splitlines():
                                ln = raw_ln.strip()
                                if len(ln) < _MIN_REPEAT_LINE_LEN:
                                    continue
                                line_repeat_counts[ln] = line_repeat_counts.get(ln, 0) + 1
                                if line_repeat_counts[ln] >= repetition_threshold:
                                    loop_detected = True
                                    break

                        if loop_detected:
                            resp.close()
                            break

                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            entry = tool_call_chunks.setdefault(idx, {"name": "", "arguments": ""})
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                entry["name"] = fn["name"]
                            if fn.get("arguments"):
                                entry["arguments"] += fn["arguments"]
                            decoded_tokens_approx += 1

                        # Loop guard: many tokens generated, still zero content and zero
                        # tool_calls committed — the model is stuck narrating/reasoning
                        # without ever acting. Cut it off instead of burning the full
                        # max_tokens budget (confirmed 2026-07-18: Bonsai on RTX 5060 Ti
                        # rambled 30K+ tokens across two calls in REAL P3 without a single
                        # new tool_call after the first one).
                        if (
                            decoded_tokens_approx > loop_guard_tokens
                            and not tool_call_chunks
                            and not content_parts
                        ):
                            loop_detected = True
                            resp.close()
                            break
        except requests.exceptions.ConnectionError as exc:
            raise LlamaCppConnectionError(
                f"Could not connect to llama.cpp server ({base_url}). "
                "Check if TurboQuant container is running."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise LlamaCppConnectionError(
                f"Inactivity timeout ({_CHUNK_TIMEOUT}s) — no data received from "
                f"llama.cpp ({base_url})."
            ) from exc

        output_text = "".join(content_parts) or "".join(reasoning_parts)

        tool_calls: list[dict] | None = None
        truncated_tool_call = False
        if tool_call_chunks:
            parsed = []
            for entry in tool_call_chunks.values():
                if not entry["name"]:
                    continue
                try:
                    args = json.loads(entry["arguments"]) if entry["arguments"] else {}
                except json.JSONDecodeError:
                    # The arguments string got cut off mid-JSON — almost
                    # always max_tokens hit before a large argument (e.g.
                    # write_file's content) finished streaming. Silently
                    # defaulting to {} used to call the tool with no
                    # arguments at all, producing a generic Python
                    # "missing required positional arguments" error that
                    # gave the model no clue what actually went wrong — it
                    # would just retry the identical (still-empty) call and
                    # trip the stuck-loop guard instead of splitting the
                    # content up. Confirmed 2026-07-20, FORGE F5:
                    # quality_report.md never got written this way, 5
                    # identical failing write_file() calls in a row.
                    # Drop this call entirely and surface the real cause in
                    # output_text below instead of pretending it's a valid
                    # (empty) call.
                    truncated_tool_call = True
                    continue
                parsed.append({"name": entry["name"], "arguments": args})
            if parsed:
                tool_calls = parsed

        if truncated_tool_call:
            note = (
                "[SYSTEM NOTE: your last tool call was cut off before its "
                "arguments finished — the content was too long to fit in one "
                "response. Split it across multiple write_file/append_file "
                "calls (write_file first, then append_file for the rest) "
                "instead of one large call.]"
            )
            output_text = f"{output_text}\n\n{note}" if output_text else note

        if not output_text and not tool_calls and not loop_detected:
            raise LlamaCppResponseError(
                f"llama.cpp response has no content or tool_calls. "
                f"finish_reason={finish_reason!r}"
            )

        return ProviderResponse(
            provider="llamacpp",
            model=request.model,
            output_text=output_text,
            raw_response={"reasoning_content": "".join(reasoning_parts), "finish_reason": finish_reason},
            tool_calls=tool_calls,
            metadata={
                "endpoint": f"{base_url}/v1/chat/completions",
                "timeout_seconds": total_timeout,
                "loop_detected": loop_detected,
                "decoded_tokens_approx": decoded_tokens_approx,
            },
        )
