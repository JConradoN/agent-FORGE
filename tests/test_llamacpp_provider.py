"""Smoke tests for LlamaCppProvider — no live server required."""
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


# ── payload generation ─────────────────────────────────────────────────────────

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


_TEXT_RESPONSE = {
    "choices": [{"message": {"content": "Hello!", "tool_calls": None}, "finish_reason": "stop"}]
}


def _capture_payload(request: ProviderRequest, response_data: dict) -> dict:
    """Call provider.generate() with mocked post; return the captured payload."""
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured.update(json or {})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_data
        return mock_resp

    provider = _make_provider()
    with patch("agentforge.providers.llamacpp.requests.post", side_effect=fake_post):
        provider.generate(request)
    return captured


def test_enable_thinking_false_in_payload():
    """chat_template_kwargs must set enable_thinking=False to suppress Qwen3 reasoning."""
    req = _make_request(input_text="Hello")
    payload = _capture_payload(req, _TEXT_RESPONSE)
    kwargs = payload.get("chat_template_kwargs", {})
    assert kwargs.get("enable_thinking") is False, (
        "enable_thinking must be False — /no_think in user messages does NOT work on llama.cpp"
    )


def test_user_message_not_modified():
    """Provider must NOT inject /no_think or any prefix into user message content."""
    req = _make_request(input_text="plain question")
    payload = _capture_payload(req, _TEXT_RESPONSE)
    user_msgs = [m for m in payload.get("messages", []) if m["role"] == "user"]
    assert user_msgs[-1]["content"] == "plain question"


# ── tool call parsing ──────────────────────────────────────────────────────────

_TOOL_CALL_RESPONSE = {
    "choices": [{
        "message": {
            "content": "",
            "tool_calls": [{
                "id": "xYZ123",
                "type": "function",
                "function": {
                    "name": "http_get",
                    "arguments": '{"url": "https://example.com"}',
                },
            }],
        },
        "finish_reason": "tool_calls",
    }]
}


def test_provider_parses_tool_calls():
    req = _make_request(input_text="Fetch something")
    provider = _make_provider()
    with patch("agentforge.providers.llamacpp.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = _TOOL_CALL_RESPONSE
        resp = provider.generate(req)
    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["name"] == "http_get"
    assert resp.tool_calls[0]["arguments"]["url"] == "https://example.com"


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
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"
    with patch("agentforge.providers.llamacpp.requests.post", return_value=mock_resp):
        with pytest.raises(LlamaCppResponseError):
            provider.generate(req)


def test_provider_raises_when_response_has_no_content_or_tools():
    req = _make_request(input_text="Hello")
    provider = _make_provider()
    empty_response = {"choices": [{"message": {"content": "", "tool_calls": None}, "finish_reason": "stop"}]}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = empty_response
    with patch("agentforge.providers.llamacpp.requests.post", return_value=mock_resp):
        with pytest.raises(LlamaCppResponseError):
            provider.generate(req)


def test_timeout_is_tuple():
    """Verify the request uses a (connect, read) timeout tuple."""
    req = _make_request(input_text="test")
    provider = _make_provider()
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["timeout"] = timeout
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _TEXT_RESPONSE
        return mock_resp

    with patch("agentforge.providers.llamacpp.requests.post", side_effect=fake_post):
        provider.generate(req)

    assert isinstance(captured["timeout"], tuple), "timeout deve ser tupla (connect, read)"
    connect_t, read_t = captured["timeout"]
    assert connect_t > 0
    assert read_t > connect_t
