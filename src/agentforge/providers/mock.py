from __future__ import annotations

from agentforge.providers.base import BaseProvider, ProviderRequest, ProviderResponse


class MockProvider(BaseProvider):
    name = "mock"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        turn = len(request.history) // 2 + 1
        suffix = f" [turn {turn}]" if request.history else ""
        return ProviderResponse(
            provider="mock",
            model=request.model,
            output_text=f"MOCK_PROVIDER_RESPONSE{suffix}: {request.input_text}",
            raw_response={
                "agent_id": request.agent_id,
                "model": request.model,
                "history_turns": len(request.history) // 2,
            },
            metadata={"mode": "mock"},
        )
