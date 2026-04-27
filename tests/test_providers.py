from __future__ import annotations

import pytest

from agentforge.providers.base import BaseProvider, ProviderRequest, ProviderResponse
from agentforge.providers.mock import MockProvider
from agentforge.providers.registry import (
    ProviderNotImplementedError,
    ProviderRegistry,
    get_default_registry,
)


# ---------------------------------------------------------------------------
# ProviderRequest / ProviderResponse
# ---------------------------------------------------------------------------

class TestProviderModels:
    def test_request_requires_agent_id_and_input(self) -> None:
        req = ProviderRequest(agent_id="x", input_text="hello")
        assert req.agent_id == "x"
        assert req.input_text == "hello"

    def test_request_optional_fields_default(self) -> None:
        req = ProviderRequest(agent_id="x", input_text="hi")
        assert req.system_prompt is None
        assert req.model is None
        assert req.metadata == {}

    def test_response_requires_provider_and_output(self) -> None:
        resp = ProviderResponse(provider="mock", output_text="hi")
        assert resp.provider == "mock"
        assert resp.output_text == "hi"

    def test_response_optional_fields_default(self) -> None:
        resp = ProviderResponse(provider="mock", output_text="hi")
        assert resp.model is None
        assert resp.raw_response is None
        assert resp.metadata == {}


# ---------------------------------------------------------------------------
# MockProvider
# ---------------------------------------------------------------------------

class TestMockProvider:
    def test_is_base_provider(self) -> None:
        assert issubclass(MockProvider, BaseProvider)

    def test_name(self) -> None:
        assert MockProvider.name == "mock"

    def test_generate_returns_provider_response(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="agent1", input_text="Olá")
        resp = provider.generate(req)
        assert isinstance(resp, ProviderResponse)

    def test_generate_output_is_deterministic(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="agent1", input_text="Olá")
        assert provider.generate(req).output_text == provider.generate(req).output_text

    def test_generate_output_contains_input(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="agent1", input_text="Teste de entrada")
        resp = provider.generate(req)
        assert "Teste de entrada" in resp.output_text

    def test_generate_output_has_mock_prefix(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="agent1", input_text="hello")
        resp = provider.generate(req)
        assert resp.output_text.startswith("MOCK_PROVIDER_RESPONSE:")

    def test_generate_provider_field(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="a", input_text="x")
        resp = provider.generate(req)
        assert resp.provider == "mock"

    def test_generate_model_forwarded(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="a", input_text="x", model="gemma4:e4b")
        resp = provider.generate(req)
        assert resp.model == "gemma4:e4b"

    def test_generate_raw_response_is_dict(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="a", input_text="x")
        resp = provider.generate(req)
        assert isinstance(resp.raw_response, dict)

    def test_generate_metadata_mode_mock(self) -> None:
        provider = MockProvider()
        req = ProviderRequest(agent_id="a", input_text="x")
        resp = provider.generate(req)
        assert resp.metadata.get("mode") == "mock"


# ---------------------------------------------------------------------------
# ProviderRegistry
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def test_register_and_get(self) -> None:
        registry = ProviderRegistry()
        registry.register("mock", MockProvider)
        assert registry.get("mock") is MockProvider

    def test_lookup_case_insensitive(self) -> None:
        registry = ProviderRegistry()
        registry.register("Mock", MockProvider)
        assert registry.get("MOCK") is MockProvider
        assert registry.get("mock") is MockProvider
        assert registry.get("Mock") is MockProvider

    def test_create_returns_instance(self) -> None:
        registry = ProviderRegistry()
        registry.register("mock", MockProvider)
        provider = registry.create("mock")
        assert isinstance(provider, MockProvider)

    def test_list_names_sorted(self) -> None:
        registry = ProviderRegistry()
        registry.register("mock", MockProvider)
        assert "mock" in registry.list_names()

    def test_unknown_provider_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotImplementedError):
            registry.get("ollama")

    def test_unknown_provider_error_message_contains_name(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotImplementedError, match="ollama"):
            registry.get("ollama")

    def test_create_unknown_provider_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotImplementedError):
            registry.create("ollama")


# ---------------------------------------------------------------------------
# get_default_registry
# ---------------------------------------------------------------------------

class TestDefaultRegistry:
    def test_mock_is_registered(self) -> None:
        registry = get_default_registry()
        assert "mock" in registry.list_names()

    def test_ollama_is_registered(self) -> None:
        registry = get_default_registry()
        assert "ollama" in registry.list_names()

    def test_create_mock_works(self) -> None:
        registry = get_default_registry()
        provider = registry.create("mock")
        assert isinstance(provider, MockProvider)

    def test_mock_lookup_case_insensitive(self) -> None:
        registry = get_default_registry()
        assert registry.get("MOCK") is MockProvider

    def test_create_ollama_returns_instance(self) -> None:
        from agentforge.providers.ollama import OllamaProvider

        registry = get_default_registry()
        provider = registry.create("ollama")
        assert isinstance(provider, OllamaProvider)
