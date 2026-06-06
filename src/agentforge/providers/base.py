from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    input_text: str
    system_prompt: str | None = None
    model: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tools_schema: list[dict[str, Any]] | None = None  # OpenAI function format


class ProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None = None
    output_text: str
    raw_response: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] | None = None  # model-requested tool calls


class ProviderError(Exception):
    """Exceção base para todos os erros de provider."""


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse: ...
