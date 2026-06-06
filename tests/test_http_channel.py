from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from agentforge.channels.http import create_app
from agentforge.core.agent_models import (
    AgentIdentity, AgentPersona, AgentSpec, ChannelSpec,
    DeploymentSpec, EvaluationSpec, GuardrailSpec, MemorySpec,
    ModelPolicySpec, OutputSpec, WorkflowSpec,
)
from agentforge.core.validation import save_agent_spec
from agentforge.generators.agent_files import build_runtime_config, build_tools_config
from agentforge.runtime.engine import AgentRuntime


def _make_runtime(tmp_path: Path) -> AgentRuntime:
    spec = AgentSpec(
        spec_version="0.1",
        agent=AgentIdentity(id="http_agent", name="HTTP Agent", purpose="Test HTTP channel"),
        persona=AgentPersona(tone="direto", style="técnico"),
        channel=ChannelSpec(type="http"),
        tools=[],
        memory=MemorySpec(type="none", enabled=False),
        output=OutputSpec(mode="text"),
        guardrails=GuardrailSpec(),
        eval=EvaluationSpec(),
        deployment=DeploymentSpec(provider="mock"),
        model_policy=ModelPolicySpec(default_model="qwen3.5:9b"),
        workflow=WorkflowSpec(mode="respond_or_tool"),
    )
    agent_dir = tmp_path / "http_agent"
    agent_dir.mkdir()
    save_agent_spec(agent_dir / "agent.yaml", spec)
    with (agent_dir / "runtime.yaml").open("w") as fh:
        yaml.safe_dump(build_runtime_config(spec), fh, allow_unicode=True)
    with (agent_dir / "tools.yaml").open("w") as fh:
        yaml.safe_dump(build_tools_config(spec), fh, allow_unicode=True)
    return AgentRuntime.from_agent_dir(agent_dir)


class TestHealthEndpoint:
    def test_health_returns_ok(self, tmp_path: Path) -> None:
        client = TestClient(create_app(_make_runtime(tmp_path)))
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_returns_agent_info(self, tmp_path: Path) -> None:
        client = TestClient(create_app(_make_runtime(tmp_path)))
        data = client.get("/health").json()
        assert data["agent_id"] == "http_agent"
        assert data["agent_name"] == "HTTP Agent"
        assert data["model"] == "qwen3.5:9b"
        assert data["provider"] == "mock"


class TestRunEndpoint:
    def test_run_returns_output(self, tmp_path: Path) -> None:
        client = TestClient(create_app(_make_runtime(tmp_path)))
        resp = client.post("/run", json={"input": "Olá"})
        assert resp.status_code == 200
        data = resp.json()
        assert "output" in data
        assert len(data["output"]) > 0

    def test_run_returns_agent_id(self, tmp_path: Path) -> None:
        client = TestClient(create_app(_make_runtime(tmp_path)))
        data = client.post("/run", json={"input": "teste"}).json()
        assert data["agent_id"] == "http_agent"

    def test_run_returns_latency_ms(self, tmp_path: Path) -> None:
        client = TestClient(create_app(_make_runtime(tmp_path)))
        data = client.post("/run", json={"input": "teste"}).json()
        assert isinstance(data["latency_ms"], int)
        assert data["latency_ms"] >= 0

    def test_run_accepts_metadata(self, tmp_path: Path) -> None:
        client = TestClient(create_app(_make_runtime(tmp_path)))
        resp = client.post("/run", json={"input": "teste", "metadata": {"source": "n8n"}})
        assert resp.status_code == 200

    def test_run_missing_input_returns_422(self, tmp_path: Path) -> None:
        client = TestClient(create_app(_make_runtime(tmp_path)))
        resp = client.post("/run", json={})
        assert resp.status_code == 422

    def test_run_creates_jsonl_log(self, tmp_path: Path) -> None:
        runtime = _make_runtime(tmp_path)
        client = TestClient(create_app(runtime))
        client.post("/run", json={"input": "teste"})
        runs_file = runtime.root_dir / "runs" / "runs.jsonl"
        assert runs_file.exists()
        assert runs_file.stat().st_size > 0
