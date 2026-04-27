from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

from agentforge.providers.base import ProviderResponse, ProviderRequest
from agentforge.providers.ollama import (
    OllamaConnectionError,
    OllamaProvider,
    OllamaProviderError,
    OllamaResponseError,
)

_FAKE_DATA = {
    "model": "gemma4:e4b",
    "response": "Resposta gerada pelo Ollama.",
    "done": True,
    "context": [],
    "total_duration": 1000,
}


def _mock_resp(status: int = 200, data: dict | None = None) -> Mock:
    r = Mock()
    r.status_code = status
    r.json.return_value = data if data is not None else _FAKE_DATA
    r.text = str(data or _FAKE_DATA)
    return r


def _req(**kwargs) -> ProviderRequest:
    return ProviderRequest(
        agent_id="test_agent",
        input_text=kwargs.get("input_text", "Olá"),
        model=kwargs.get("model", "gemma4:e4b"),
        system_prompt=kwargs.get("system_prompt"),
    )


# ---------------------------------------------------------------------------
# Estrutura e herança
# ---------------------------------------------------------------------------

class TestOllamaProviderStructure:
    def test_is_base_provider(self) -> None:
        from agentforge.providers.base import BaseProvider
        assert issubclass(OllamaProvider, BaseProvider)

    def test_name(self) -> None:
        assert OllamaProvider.name == "ollama"

    def test_connection_error_is_subclass_of_provider_error(self) -> None:
        assert issubclass(OllamaConnectionError, OllamaProviderError)

    def test_response_error_is_subclass_of_provider_error(self) -> None:
        assert issubclass(OllamaResponseError, OllamaProviderError)

    def test_provider_error_is_subclass_of_base_provider_error(self) -> None:
        from agentforge.providers.base import ProviderError
        assert issubclass(OllamaProviderError, ProviderError)


# ---------------------------------------------------------------------------
# Sucesso
# ---------------------------------------------------------------------------

class TestOllamaProviderSuccess:
    def test_generate_returns_provider_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp()))
        resp = OllamaProvider().generate(_req())
        assert isinstance(resp, ProviderResponse)

    def test_generate_provider_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp()))
        resp = OllamaProvider().generate(_req())
        assert resp.provider == "ollama"

    def test_generate_output_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp()))
        resp = OllamaProvider().generate(_req())
        assert resp.output_text == "Resposta gerada pelo Ollama."

    def test_generate_model_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp()))
        resp = OllamaProvider().generate(_req(model="qwen3:5b"))
        assert resp.model == "qwen3:5b"

    def test_generate_raw_response_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp()))
        resp = OllamaProvider().generate(_req())
        assert resp.raw_response == _FAKE_DATA

    def test_generate_metadata_has_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp()))
        resp = OllamaProvider().generate(_req())
        assert "endpoint" in resp.metadata
        assert "11434" in resp.metadata["endpoint"]

    def test_generate_metadata_has_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp()))
        resp = OllamaProvider().generate(_req())
        assert "timeout_seconds" in resp.metadata


# ---------------------------------------------------------------------------
# Payload enviado ao Ollama
# ---------------------------------------------------------------------------

class TestOllamaProviderPayload:
    def test_url_contains_generate_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_post = Mock(return_value=_mock_resp())
        monkeypatch.setattr(requests, "post", mock_post)
        OllamaProvider().generate(_req())
        url = mock_post.call_args[0][0]
        assert "localhost:11434" in url
        assert "/api/generate" in url

    def test_payload_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_post = Mock(return_value=_mock_resp())
        monkeypatch.setattr(requests, "post", mock_post)
        OllamaProvider().generate(_req(model="gemma4:e4b"))
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "gemma4:e4b"

    def test_payload_stream_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_post = Mock(return_value=_mock_resp())
        monkeypatch.setattr(requests, "post", mock_post)
        OllamaProvider().generate(_req())
        payload = mock_post.call_args[1]["json"]
        assert payload["stream"] is False

    def test_payload_has_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_post = Mock(return_value=_mock_resp())
        monkeypatch.setattr(requests, "post", mock_post)
        OllamaProvider().generate(_req(input_text="oi"))
        payload = mock_post.call_args[1]["json"]
        assert "prompt" in payload

    def test_payload_prompt_without_system_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_post = Mock(return_value=_mock_resp())
        monkeypatch.setattr(requests, "post", mock_post)
        OllamaProvider().generate(_req(input_text="só input"))
        payload = mock_post.call_args[1]["json"]
        assert payload["prompt"] == "só input"

    def test_payload_prompt_with_system_prompt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_post = Mock(return_value=_mock_resp())
        monkeypatch.setattr(requests, "post", mock_post)
        OllamaProvider().generate(_req(input_text="Pergunta", system_prompt="Você é um assistente."))
        payload = mock_post.call_args[1]["json"]
        assert "Você é um assistente." in payload["prompt"]
        assert "Pergunta" in payload["prompt"]

    def test_payload_has_explicit_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_post = Mock(return_value=_mock_resp())
        monkeypatch.setattr(requests, "post", mock_post)
        OllamaProvider().generate(_req())
        kwargs = mock_post.call_args[1]
        assert "timeout" in kwargs


# ---------------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------------

class TestOllamaProviderErrors:
    def test_connection_error_raises_ollama_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            requests, "post",
            Mock(side_effect=requests.exceptions.ConnectionError("refused")),
        )
        with pytest.raises(OllamaConnectionError):
            OllamaProvider().generate(_req())

    def test_timeout_raises_ollama_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            requests, "post",
            Mock(side_effect=requests.exceptions.Timeout("timed out")),
        )
        with pytest.raises(OllamaConnectionError):
            OllamaProvider().generate(_req())

    def test_connection_error_message_mentions_localhost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            requests, "post",
            Mock(side_effect=requests.exceptions.ConnectionError("refused")),
        )
        with pytest.raises(OllamaConnectionError, match="localhost"):
            OllamaProvider().generate(_req())

    def test_http_non_200_raises_response_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp(status=500)))
        with pytest.raises(OllamaResponseError):
            OllamaProvider().generate(_req())

    def test_http_error_message_contains_status_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp(status=404)))
        with pytest.raises(OllamaResponseError, match="404"):
            OllamaProvider().generate(_req())

    def test_missing_response_field_raises_response_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bad_data = {"model": "x", "done": True}
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp(data=bad_data)))
        with pytest.raises(OllamaResponseError):
            OllamaProvider().generate(_req())

    def test_missing_response_field_error_lists_received_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bad_data = {"model": "x", "done": True}
        monkeypatch.setattr(requests, "post", Mock(return_value=_mock_resp(data=bad_data)))
        with pytest.raises(OllamaResponseError, match="model"):
            OllamaProvider().generate(_req())
