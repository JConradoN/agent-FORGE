from __future__ import annotations

import json
import os

import requests

from agentforge.providers.base import BaseProvider, ProviderError, ProviderRequest, ProviderResponse

_DEFAULT_HOST = "http://localhost:8082"
_DEFAULT_TIMEOUT = 900
_CONNECT_TIMEOUT = 10  # seconds to establish TCP connection


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
            "stream": False,
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
        timeout = int(os.environ.get("LLAMACPP_TIMEOUT", str(_DEFAULT_TIMEOUT)))

        try:
            response = requests.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                timeout=(_CONNECT_TIMEOUT, timeout),
            )
        except requests.exceptions.ConnectionError as exc:
            raise LlamaCppConnectionError(
                f"Could not connect to llama.cpp server ({base_url}). "
                "Check if TurboQuant container is running."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise LlamaCppConnectionError(
                f"Timeout ({timeout}s) waiting for response from llama.cpp ({base_url})."
            ) from exc

        if response.status_code != 200:
            raise LlamaCppResponseError(
                f"llama.cpp returned status {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise LlamaCppResponseError("llama.cpp response is not valid JSON.") from exc

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Prefer content; fall back to reasoning_content if content is empty.
        output_text = message.get("content") or message.get("reasoning_content") or ""

        raw_tcs = message.get("tool_calls") or []
        tool_calls: list[dict] | None = None
        if raw_tcs:
            parsed = []
            for tc in raw_tcs:
                fn = tc.get("function", {})
                name = fn.get("name")
                if not name:
                    continue
                args_raw = fn.get("arguments", "{}")
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = args_raw
                parsed.append({"name": name, "arguments": args})
            if parsed:
                tool_calls = parsed

        if not output_text and not tool_calls:
            raise LlamaCppResponseError(
                f"llama.cpp response has no content or tool_calls. "
                f"finish_reason={choice.get('finish_reason')!r} "
                f"message_keys={list(message.keys())}"
            )

        return ProviderResponse(
            provider="llamacpp",
            model=request.model,
            output_text=output_text,
            raw_response=data,
            tool_calls=tool_calls,
            metadata={
                "endpoint": f"{base_url}/v1/chat/completions",
                "timeout_seconds": timeout,
            },
        )
