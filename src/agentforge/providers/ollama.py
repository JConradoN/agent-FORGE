from __future__ import annotations

import requests

from agentforge.providers.base import BaseProvider, ProviderError, ProviderRequest, ProviderResponse

_BASE_URL = "http://localhost:11434"
_TIMEOUT = 30  # seconds


class OllamaProviderError(ProviderError):
    """Erro base do provider Ollama."""


class OllamaConnectionError(OllamaProviderError):
    """Falha de conexão ou timeout com o Ollama local."""


class OllamaResponseError(OllamaProviderError):
    """Resposta HTTP inválida ou formato inesperado do Ollama."""


class OllamaProvider(BaseProvider):
    name = "ollama"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if request.history:
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

        payload = {
            "model": request.model,
            "messages": messages,
            "stream": False,
        }

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
        output_text = message.get("content")
        if output_text is None:
            raise OllamaResponseError(
                f"Resposta do Ollama (chat) não contém message.content. "
                f"Campos recebidos: {list(data.keys())}"
            )

        return ProviderResponse(
            provider="ollama",
            model=request.model,
            output_text=output_text,
            raw_response=data,
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
