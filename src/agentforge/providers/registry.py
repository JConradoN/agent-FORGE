from __future__ import annotations

from agentforge.providers.base import BaseProvider, ProviderError


class ProviderNotImplementedError(ProviderError):
    pass


class ProviderRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, type[BaseProvider]] = {}

    def register(self, name: str, provider_cls: type[BaseProvider]) -> None:
        self._registry[name.lower()] = provider_cls

    def get(self, name: str) -> type[BaseProvider]:
        key = name.lower()
        try:
            return self._registry[key]
        except KeyError:
            known = ", ".join(sorted(self._registry)) or "nenhum"
            raise ProviderNotImplementedError(
                f"Provider '{name}' não está disponível. Providers registrados: {known or 'nenhum'}"
            ) from None

    def create(self, name: str) -> BaseProvider:
        return self.get(name)()

    def list_names(self) -> list[str]:
        return sorted(self._registry)


def get_default_registry() -> ProviderRegistry:
    from agentforge.providers.mock import MockProvider
    from agentforge.providers.ollama import OllamaProvider

    registry = ProviderRegistry()
    registry.register("mock", MockProvider)
    registry.register("ollama", OllamaProvider)
    return registry
