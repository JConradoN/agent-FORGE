from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    purpose: str


class AgentPersona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: str
    style: str
    personality: str | None = None


class ChannelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    interface: str | None = None


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    required: bool = False
    description: str | None = None
    category: str | None = None
    status: str = "stable"         # stable | optional | experimental
    when_to_use: str | None = None
    when_not_to_use: str | None = None
    input_schema: str | None = None
    output_schema: str | None = None


class MemorySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    enabled: bool = False
    max_turns: int = 0      # 0 = unlimited
    policy: str = "truncate"


class OutputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    format: str | None = None


class EvaluationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_score_enabled: bool = False
    notes: str | None = None
    criteria: list[str] = []        # criteria for the judge to evaluate
    judge_model: str | None = None  # scoring model (e.g., "gemma4:e4b" or "gemini-2.5-flash")


class GuardrailSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must: list[str] = []
    must_not: list[str] = []
    optional: list[str] = []


class DeploymentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "ollama"


class ModelPolicySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_model: str
    fallback_model: str | None = None


class AgentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    agent_dir: str
    description: str | None = None


class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    multi_turn: bool = False
    max_tool_cycles: int = 3      # maximum rounds of tool calling per run
    reflection_rounds: int = 0    # rounds of self-criticism after final response
    agents: list[AgentRef] = []   # workers available for delegation


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec_version: str
    agent: AgentIdentity
    persona: AgentPersona
    channel: ChannelSpec
    tools: list[ToolSpec] = []
    memory: MemorySpec
    output: OutputSpec
    guardrails: GuardrailSpec
    eval: EvaluationSpec
    deployment: DeploymentSpec = Field(default_factory=DeploymentSpec)
    model_policy: ModelPolicySpec
    workflow: WorkflowSpec

    @field_validator("spec_version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> str:
        return str(v)
