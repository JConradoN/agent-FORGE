"""Smoke tests for LlamaCppProvider — no live server required.

Provider talks to llama.cpp via streaming (stream=True) since 2026-07-18 —
needed for the real total-timeout and loop-guard checks (see llamacpp.py).
Mocks below build fake requests.Response objects usable as
`with requests.post(...) as resp:` and exercise `resp.iter_lines()`.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from agentforge.providers.base import ProviderRequest
from agentforge.providers.llamacpp import (
    LlamaCppConnectionError,
    LlamaCppProvider,
    LlamaCppResponseError,
    _normalize_messages,
)


# ── _normalize_messages ────────────────────────────────────────────────────────

def test_normalize_passthrough_plain_messages():
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    result = _normalize_messages(msgs)
    assert result == msgs


def test_normalize_tool_call_adds_type_and_id():
    msgs = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "write_file", "arguments": {"path": "f.txt", "content": "x"}}}
            ],
        }
    ]
    result = _normalize_messages(msgs)
    assert len(result) == 1
    tc = result[0]["tool_calls"][0]
    assert tc["type"] == "function"
    assert tc["id"].startswith("call_")
    assert tc["function"]["name"] == "write_file"
    # arguments must be a JSON string
    args = json.loads(tc["function"]["arguments"])
    assert args["path"] == "f.txt"


def test_normalize_tool_result_gets_tool_call_id():
    msgs = [
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "http_get", "arguments": {"url": "http://x"}}}
            ],
        },
        {"role": "tool", "content": '{"data": 1}', "name": "http_get"},
    ]
    result = _normalize_messages(msgs)
    call_id = result[0]["tool_calls"][0]["id"]
    assert result[1]["tool_call_id"] == call_id


def test_normalize_multiple_tool_calls_paired_in_order():
    msgs = [
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "tool_a", "arguments": {}}},
                {"function": {"name": "tool_b", "arguments": {}}},
            ],
        },
        {"role": "tool", "content": "result_a", "name": "tool_a"},
        {"role": "tool", "content": "result_b", "name": "tool_b"},
    ]
    result = _normalize_messages(msgs)
    assert result[1]["tool_call_id"] == result[0]["tool_calls"][0]["id"]
    assert result[2]["tool_call_id"] == result[0]["tool_calls"][1]["id"]


def test_normalize_args_string_kept_as_string():
    """If args are already a string (e.g. re-normalising), keep them."""
    msgs = [
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "run_bash", "arguments": '{"command":"ls"}'}}
            ],
        }
    ]
    result = _normalize_messages(msgs)
    tc = result[0]["tool_calls"][0]
    assert isinstance(tc["function"]["arguments"], str)
    assert json.loads(tc["function"]["arguments"])["command"] == "ls"


# ── streaming SSE test helpers ──────────────────────────────────────────────────

def _sse(chunk: dict) -> str:
    return f"data: {json.dumps(chunk)}"


def _content_chunk(text: str, finish_reason: str | None = None) -> str:
    return _sse({"choices": [{"delta": {"content": text}, "finish_reason": finish_reason}]})


def _reasoning_chunk(text: str, finish_reason: str | None = None) -> str:
    return _sse({"choices": [{"delta": {"reasoning_content": text}, "finish_reason": finish_reason}]})


def _tool_call_chunks(name: str, arguments_json_str: str, call_id: str = "call_abc") -> list[str]:
    first = _sse({
        "choices": [{
            "delta": {"tool_calls": [{"index": 0, "id": call_id, "type": "function",
                                       "function": {"name": name, "arguments": ""}}]},
            "finish_reason": None,
        }]
    })
    second = _sse({
        "choices": [{
            "delta": {"tool_calls": [{"index": 0, "function": {"arguments": arguments_json_str}}]},
            "finish_reason": "tool_calls",
        }]
    })
    return [first, second]


_DONE = "data: [DONE]"


def _stream_resp(lines: list[str], status_code: int = 200, text: str = "") -> MagicMock:
    """Mock requests.Response usable as `with requests.post(...) as resp:`.

    iter_lines() is called with decode_unicode=False in production (see
    llamacpp.py — relying on requests' encoding guess mojibakes non-ASCII
    SSE content), so real callers get bytes back and decode explicitly.
    Encode here to match that contract instead of the old str-based mock.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.iter_lines.return_value = iter(line.encode("utf-8") for line in lines)
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


# ── payload generation ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _no_gpu_broker():
    """Provider agora coordena via fox-gpu-broker (ver gpu_broker_client.acquire_gpu).
    Este módulo é 'no live server required' — bypassa o broker pra manter isolado."""
    from contextlib import contextmanager

    @contextmanager
    def _noop(*args, **kwargs):
        yield

    with patch("agentforge.providers.llamacpp.acquire_gpu", side_effect=_noop):
        yield


def _make_provider():
    return LlamaCppProvider()


def _make_request(input_text: str = "", history: list | None = None) -> ProviderRequest:
    return ProviderRequest(
        agent_id="test",
        input_text=input_text,
        system_prompt="Be helpful.",
        model="test-model",
        history=history or [],
        tools_schema=None,
    )


_TEXT_STREAM = [_content_chunk("Hello!", finish_reason="stop"), _DONE]


def _capture_payload(request: ProviderRequest, stream_lines: list[str]) -> dict:
    """Call provider.generate() with mocked post; return the captured payload."""
    captured = {}

    def fake_post(url, json=None, stream=None, timeout=None, **kwargs):
        captured.update(json or {})
        return _stream_resp(stream_lines)

    provider = _make_provider()
    with patch("agentforge.providers.llamacpp.requests.post", side_effect=fake_post):
        provider.generate(request)
    return captured


def test_enable_thinking_false_by_default():
    """With no LLAMACPP_THINKING_BUDGET set, enable_thinking must be False."""
    req = _make_request(input_text="Hello")
    payload = _capture_payload(req, _TEXT_STREAM)
    kwargs = payload.get("chat_template_kwargs", {})
    assert kwargs.get("enable_thinking") is False, (
        "enable_thinking must be False by default — /no_think in user messages does NOT work on llama.cpp"
    )
    assert payload.get("max_tokens") == 8192
    assert payload.get("stream") is True


def test_thinking_budget_enables_thinking(monkeypatch):
    """When LLAMACPP_THINKING_BUDGET is set, enable_thinking=True and max_tokens grows."""
    monkeypatch.setenv("LLAMACPP_THINKING_BUDGET", "500")
    req = _make_request(input_text="Complex task")
    payload = _capture_payload(req, _TEXT_STREAM)
    kwargs = payload.get("chat_template_kwargs", {})
    assert kwargs.get("enable_thinking") is True
    assert payload.get("max_tokens") == 500 + 8192


def test_user_message_not_modified():
    """Provider must NOT inject /no_think or any prefix into user message content."""
    req = _make_request(input_text="plain question")
    payload = _capture_payload(req, _TEXT_STREAM)
    user_msgs = [m for m in payload.get("messages", []) if m["role"] == "user"]
    assert user_msgs[-1]["content"] == "plain question"


def test_non_ascii_content_survives_streaming_intact():
    """Regression test: iter_lines(decode_unicode=True) lets requests guess the
    SSE stream's encoding, and llama.cpp doesn't declare charset=utf-8 — requests
    silently falls back to Latin-1 for text/* without one, mojibaking any accented
    content (confirmed 2026-07-20 with PT-BR guardrail phrases). The provider must
    decode explicitly as UTF-8 instead of trusting the guess.
    """
    req = _make_request(input_text="responda em português")
    provider = _make_provider()
    text = "EXTRAÇÃO CONCLUÍDA: 6 agentes encontrados, 2 com erro"
    lines = [_content_chunk(text, finish_reason="stop"), _DONE]
    with patch("agentforge.providers.llamacpp.requests.post", return_value=_stream_resp(lines)):
        resp = provider.generate(req)
    assert resp.output_text == text


# ── tool call parsing ──────────────────────────────────────────────────────────

def test_provider_parses_tool_calls():
    req = _make_request(input_text="Fetch something")
    provider = _make_provider()
    lines = _tool_call_chunks("http_get", '{"url": "https://example.com"}') + [_DONE]
    with patch("agentforge.providers.llamacpp.requests.post", return_value=_stream_resp(lines)):
        resp = provider.generate(req)
    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["name"] == "http_get"
    assert resp.tool_calls[0]["arguments"]["url"] == "https://example.com"


def test_truncated_tool_call_json_dropped_not_emptied():
    """Regression test: when a tool_call's streamed arguments JSON is cut off
    mid-object (max_tokens hit before a large argument like write_file's
    content finished — confirmed 2026-07-20, FORGE F5: quality_report.md
    never got written this way), the provider must NOT silently substitute
    an empty {} and still report the call as valid. An empty-args write_file
    call fails downstream with a generic Python TypeError that gives the
    model no clue what went wrong, so it just retries the identical (still
    truncated) call and trips the stuck-loop guard. The call must be
    dropped, and the model must get output_text explaining the real cause
    so it can retry with shorter/split content.
    """
    req = _make_request(input_text="Write a big file")
    provider = _make_provider()
    truncated_json = '{"path": "quality_report.md", "content": "## Report\\n\\nSome tex'
    lines = _tool_call_chunks("write_file", truncated_json) + [_DONE]
    with patch("agentforge.providers.llamacpp.requests.post", return_value=_stream_resp(lines)):
        resp = provider.generate(req)
    assert resp.tool_calls is None
    assert "cut off" in resp.output_text.lower()
    assert "write_file" in resp.output_text or "append_file" in resp.output_text


def test_provider_raises_on_connection_error():
    req = _make_request(input_text="Hello")
    provider = _make_provider()
    with patch(
        "agentforge.providers.llamacpp.requests.post",
        side_effect=requests.exceptions.ConnectionError("refused"),
    ):
        with pytest.raises(LlamaCppConnectionError):
            provider.generate(req)


def test_provider_raises_on_non_200():
    req = _make_request(input_text="Hello")
    provider = _make_provider()
    resp = _stream_resp([], status_code=503, text="Service Unavailable")
    with patch("agentforge.providers.llamacpp.requests.post", return_value=resp):
        with pytest.raises(LlamaCppResponseError):
            provider.generate(req)


def test_provider_raises_when_response_has_no_content_or_tools():
    req = _make_request(input_text="Hello")
    provider = _make_provider()
    with patch("agentforge.providers.llamacpp.requests.post", return_value=_stream_resp([_DONE])):
        with pytest.raises(LlamaCppResponseError):
            provider.generate(req)


def test_timeout_tuple_uses_chunk_timeout_not_total():
    """(connect, read) tuple bounds inter-chunk inactivity, not the whole call —
    the real total deadline is enforced separately (see test below)."""
    req = _make_request(input_text="test")
    provider = _make_provider()
    captured = {}

    def fake_post(url, json=None, stream=None, timeout=None, **kwargs):
        captured["timeout"] = timeout
        return _stream_resp(_TEXT_STREAM)

    with patch("agentforge.providers.llamacpp.requests.post", side_effect=fake_post):
        provider.generate(req)

    assert isinstance(captured["timeout"], tuple), "timeout deve ser tupla (connect, read)"
    connect_t, read_t = captured["timeout"]
    assert connect_t > 0
    assert read_t > connect_t


# ── loop guard + real total timeout (2026-07-18, RTX 5060 Ti Bonsai incident) ──

def test_loop_detected_when_reasoning_exceeds_budget_with_no_action():
    """Many reasoning_content chunks, never a tool_call or content chunk —
    provider must flag loop_detected instead of raising or hanging."""
    req = _make_request(input_text="Do something complex")
    provider = _make_provider()
    # one reasoning chunk per token; default loop guard is 6000 tokens
    lines = [_reasoning_chunk("blah ") for _ in range(6200)] + [_DONE]
    with patch("agentforge.providers.llamacpp.requests.post", return_value=_stream_resp(lines)):
        resp = provider.generate(req)
    assert resp.metadata["loop_detected"] is True
    assert resp.tool_calls is None
    assert resp.output_text  # partial reasoning text, not empty


def test_no_loop_detected_when_tool_call_arrives_before_threshold():
    """Reasoning followed by an actual tool_call must NOT be flagged as a loop,
    even if the reasoning alone was long."""
    req = _make_request(input_text="Do something complex")
    provider = _make_provider()
    lines = (
        [_reasoning_chunk("thinking... ") for _ in range(50)]
        + _tool_call_chunks("write_file", '{"path": "f.txt", "content": "x"}')
        + [_DONE]
    )
    with patch("agentforge.providers.llamacpp.requests.post", return_value=_stream_resp(lines)):
        resp = provider.generate(req)
    assert resp.metadata["loop_detected"] is False
    assert resp.tool_calls is not None
    assert resp.tool_calls[0]["name"] == "write_file"


def test_total_timeout_enforced_regardless_of_active_chunks(monkeypatch):
    """A model that keeps streaming SOMETHING forever must still be cut off at
    LLAMACPP_TIMEOUT — this is the real fix for the RTX 5060 Ti incident, where
    the old (connect, read) tuple never fired because chunks kept arriving."""
    monkeypatch.setenv("LLAMACPP_TIMEOUT", "10")
    req = _make_request(input_text="test")
    provider = _make_provider()

    # Simulate wall-clock advancing past the 10s deadline after a few chunks,
    # without actually sleeping in the test.
    clock = {"t": 0.0}

    def fake_monotonic():
        clock["t"] += 4.0
        return clock["t"]

    lines = [_content_chunk("x") for _ in range(50)] + [_DONE]
    with patch("agentforge.providers.llamacpp.requests.post", return_value=_stream_resp(lines)):
        with patch("agentforge.providers.llamacpp.time.monotonic", side_effect=fake_monotonic):
            with pytest.raises(LlamaCppConnectionError, match="Total timeout"):
                provider.generate(req)
