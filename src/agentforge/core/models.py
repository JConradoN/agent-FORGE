from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class FrameworkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    goal: str
    deployment_target: str
    default_runtime_provider: str
    optional_build_providers: list[str] = []


class FrameworkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec_version: str
    framework: FrameworkConfig

    @field_validator("spec_version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> str:
        return str(v)


class DelegationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_generation: str
    refactor: str
    test_creation: str
    documentation: str
    critique: str
    final_synthesis: str


class OrchestrationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner: str
    coding_agent: str
    analysis_agent: str
    delegation_policy: DelegationPolicy


class OrchestratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec_version: str
    orchestration: OrchestrationConfig

    @field_validator("spec_version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> str:
        return str(v)


class ValidationResult(BaseModel):
    path: str
    spec_type: str
    valid: bool
    errors: list[str] = []
