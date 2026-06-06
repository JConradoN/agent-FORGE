from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agentforge.runtime.engine import AgentRuntime


class RunRequest(BaseModel):
    input: str
    metadata: dict[str, Any] | None = None


class RunResponse(BaseModel):
    agent_id: str
    output: str
    latency_ms: int
    provider: str
    model: str
    tool_calls_log: list[dict] | None = None


class HealthResponse(BaseModel):
    status: str
    agent_id: str
    agent_name: str
    model: str
    provider: str


def create_app(runtime: AgentRuntime) -> FastAPI:
    app = FastAPI(
        title=f"AgentForge — {runtime.agent_spec.agent.name}",
        description=runtime.agent_spec.agent.purpose,
        version="0.1.0",
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            agent_id=runtime.runtime_config.agent_id,
            agent_name=runtime.agent_spec.agent.name,
            model=runtime.runtime_config.model_default,
            provider=runtime.runtime_config.provider,
        )

    @app.post("/run", response_model=RunResponse)
    def run(req: RunRequest) -> RunResponse:
        try:
            result = runtime.run(req.input, metadata=req.metadata)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return RunResponse(
            agent_id=result["agent_id"],
            output=result["output"],
            latency_ms=result["metadata"].get("latency_ms", 0),
            provider=result["provider"],
            model=result["provider_response"]["model"],
            tool_calls_log=result["metadata"].get("tool_calls_log"),
        )

    return app
