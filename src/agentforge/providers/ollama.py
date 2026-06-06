from __future__ import annotations

import requests

from agentforge.providers.base import BaseProvider, ProviderError, ProviderRequest, ProviderResponse

_BASE_URL = "http://localhost:11434"
_TIMEOUT = int(__import__("os").environ.get("OLLAMA_TIMEOUT", "900"))  # default 900s, overridable


class OllamaProviderError(ProviderError):
    """Base error for the Ollama provider."""


class OllamaConnectionError(OllamaProviderError):
    """Connection failure or timeout with local Ollama."""


class OllamaResponseError(OllamaProviderError):
    """Invalid HTTP response or unexpected format from Ollama."""


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
                f"Could not connect to local Ollama ({_BASE_URL}). "
                "Check if the service is running."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaConnectionError(
                f"Timeout ({_TIMEOUT}s) waiting for response from local Ollama ({_BASE_URL})."
            ) from exc

        if response.status_code != 200:
            raise OllamaResponseError(
                f"Ollama returned status {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaResponseError("Ollama response is not valid JSON.") from exc

        output_text = data.get("response")
        if output_text is None:
            raise OllamaResponseError(
                f"Ollama response does not contain the 'response' field. "
                f"Received fields: {list(data.keys())}"
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
            "think": False,  # disables Qwen3 thinking mode — avoids empty message.content
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
                f"Could not connect to local Ollama ({_BASE_URL}). "
                "Check if the service is running."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaConnectionError(
                f"Timeout ({_TIMEOUT}s) waiting for response from local Ollama ({_BASE_URL})."
            ) from exc

        if response.status_code != 200:
            raise OllamaResponseError(
                f"Ollama returned status {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaResponseError("Ollama response is not valid JSON.") from exc

        message = data.get("message") or {}
        output_text = message.get("content") or ""
        tool_calls_raw = message.get("tool_calls")

        # qwen3.5 com think:False às vezes coloca o output em message.thinking
        # quando tools estão no payload — usa como fallback antes de falhar.
        if not output_text and not tool_calls_raw:
            thinking = message.get("thinking") or ""
            if thinking:
                output_text = thinking
            else:
                raise OllamaResponseError(
                    f"Ollama response (chat) does not contain message.content or tool_calls. "
                    f"Received fields: {list(data.keys())}"
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
