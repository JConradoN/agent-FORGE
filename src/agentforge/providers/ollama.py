from __future__ import annotations

import requests

from agentforge.providers.base import BaseProvider, ProviderError, ProviderRequest, ProviderResponse

_BASE_URL = "http://localhost:11434"
_TIMEOUT = 120  # seconds — gemma4:e4b needs headroom on larger contexts


class OllamaProviderError(ProviderError):
    """Erro base do provider Ollama."""


class OllamaConnectionError(OllamaProviderError):
    """Falha de conexão ou timeout com o Ollama local."""


class OllamaResponseError(OllamaProviderError):
    """Resposta HTTP inválida ou formato inesperado do Ollama."""


class OllamaProvider(BaseProvider):
    name = "ollama"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if request.history or request.tools_schema:
            return self._generate_chat(request)
        return self._generate_simple(request)

    def _generate_simple(self, request: ProviderRequest) -> ProviderResponse:
        payload = {
            "model": request.model,
            "prompt": self._build_prompt(request),
            "stream": False,
        }

        try:
            response = requests.post(
                f"{_BASE_URL}/api/generate",
                json=payload,
                timeout=_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as exc:
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama local ({_BASE_URL}). "
                "Verifique se o serviço está rodando."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaConnectionError(
                f"Timeout ({_TIMEOUT}s) ao aguardar resposta do Ollama local ({_BASE_URL})."
            ) from exc

        if response.status_code != 200:
            raise OllamaResponseError(
                f"Ollama retornou status {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaResponseError("Resposta do Ollama não é JSON válido.") from exc

        output_text = data.get("response")
        if output_text is None:
            raise OllamaResponseError(
                f"Resposta do Ollama não contém o campo 'response'. "
                f"Campos recebidos: {list(data.keys())}"
            )

        return ProviderResponse(
            provider="ollama",
            model=request.model,
            output_text=output_text,
            raw_response=data,
            metadata={
                "endpoint": f"{_BASE_URL}/api/generate",
                "timeout_seconds": _TIMEOUT,
            },
        )

    def _generate_chat(self, request: ProviderRequest) -> ProviderResponse:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.history)
        messages.append({"role": "user", "content": request.input_text})

        payload: dict = {
            "model": request.model,
            "messages": messages,
            "stream": False,
        }
        if request.tools_schema:
            payload["tools"] = request.tools_schema

        try:
            response = requests.post(
                f"{_BASE_URL}/api/chat",
                json=payload,
                timeout=_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as exc:
            raise OllamaConnectionError(
                f"Não foi possível conectar ao Ollama local ({_BASE_URL}). "
                "Verifique se o serviço está rodando."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaConnectionError(
                f"Timeout ({_TIMEOUT}s) ao aguardar resposta do Ollama local ({_BASE_URL})."
            ) from exc

        if response.status_code != 200:
            raise OllamaResponseError(
                f"Ollama retornou status {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaResponseError("Resposta do Ollama não é JSON válido.") from exc

        message = data.get("message") or {}
        output_text = message.get("content") or ""
        tool_calls_raw = message.get("tool_calls")

        # When model decides to call tools, content may be empty — that's valid.
        if not output_text and not tool_calls_raw:
            raise OllamaResponseError(
                f"Resposta do Ollama (chat) não contém message.content nem tool_calls. "
                f"Campos recebidos: {list(data.keys())}"
            )

        tool_calls: list[dict] | None = None
        if tool_calls_raw:
            tool_calls = [
                {
                    "name": tc.get("function", {}).get("name"),
                    "arguments": tc.get("function", {}).get("arguments", {}),
                }
                for tc in tool_calls_raw
                if tc.get("function", {}).get("name")
            ] or None

        return ProviderResponse(
            provider="ollama",
            model=request.model,
            output_text=output_text,
            raw_response=data,
            tool_calls=tool_calls,
            metadata={
                "endpoint": f"{_BASE_URL}/api/chat",
                "timeout_seconds": _TIMEOUT,
            },
        )

    @staticmethod
    def _build_prompt(request: ProviderRequest) -> str:
        if request.system_prompt:
            return f"<System>\n{request.system_prompt}\n\n<User>\n{request.input_text}"
        return request.input_text
