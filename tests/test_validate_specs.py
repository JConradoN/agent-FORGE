from __future__ import annotations

from pathlib import Path

import pytest

from agentforge.core.models import FrameworkSpec, OrchestratorSpec, ValidationResult
from agentforge.core.validation import (
    validate_all_specs,
    validate_framework_spec,
    validate_orchestrator_spec,
)

PROJECT_ROOT = Path(__file__).parent.parent
SPECS_DIR = PROJECT_ROOT / "specs"


def test_validate_framework_spec() -> None:
    spec = validate_framework_spec(SPECS_DIR / "framework.spec.yaml")
    assert isinstance(spec, FrameworkSpec)
    assert spec.framework.name == "agents-framework"
    assert spec.framework.default_runtime_provider == "ollama"


def test_validate_orchestrator_spec() -> None:
    spec = validate_orchestrator_spec(SPECS_DIR / "orchestrator.spec.yaml")
    assert isinstance(spec, OrchestratorSpec)
    assert spec.orchestration.planner == "perplexity"
    assert spec.orchestration.delegation_policy.code_generation == "claude_code"


def test_validate_all_specs_returns_two_valid_results() -> None:
    results = validate_all_specs(PROJECT_ROOT)
    assert len(results) == 2
    assert all(isinstance(r, ValidationResult) for r in results)
    assert all(r.valid for r in results), [r.errors for r in results if not r.valid]


def test_validate_all_specs_invalid_root(tmp_path: Path) -> None:
    results = validate_all_specs(tmp_path)
    assert len(results) == 2
    assert all(not r.valid for r in results)
    assert all(r.errors for r in results)
