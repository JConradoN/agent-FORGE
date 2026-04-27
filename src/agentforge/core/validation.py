from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agentforge.core.agent_models import AgentSpec
from agentforge.core.models import (
    FrameworkSpec,
    OrchestratorSpec,
    ValidationResult,
)

SPEC_FILES = {
    "framework.spec.yaml": ("framework", FrameworkSpec),
    "orchestrator.spec.yaml": ("orchestrator", OrchestratorSpec),
}


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at top level, got {type(data).__name__}: {path}")
    return data


def validate_framework_spec(path: str | Path) -> FrameworkSpec:
    data = load_yaml_file(path)
    return FrameworkSpec.model_validate(data)


def validate_orchestrator_spec(path: str | Path) -> OrchestratorSpec:
    data = load_yaml_file(path)
    return OrchestratorSpec.model_validate(data)


def validate_agent_spec(path: str | Path) -> AgentSpec:
    data = load_yaml_file(path)
    return AgentSpec.model_validate(data)


def save_agent_spec(path: str | Path, spec: AgentSpec) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = spec.model_dump()
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def validate_all_specs(root: str | Path) -> list[ValidationResult]:
    root = Path(root)
    specs_dir = root / "specs"
    results: list[ValidationResult] = []

    for filename, (spec_type, model_cls) in SPEC_FILES.items():
        spec_path = specs_dir / filename
        try:
            data = load_yaml_file(spec_path)
            model_cls.model_validate(data)
            results.append(ValidationResult(path=str(spec_path), spec_type=spec_type, valid=True))
        except FileNotFoundError as exc:
            results.append(
                ValidationResult(
                    path=str(spec_path),
                    spec_type=spec_type,
                    valid=False,
                    errors=[str(exc)],
                )
            )
        except ValidationError as exc:
            errors = [f"{e['loc']}: {e['msg']}" for e in exc.errors()]
            results.append(
                ValidationResult(
                    path=str(spec_path),
                    spec_type=spec_type,
                    valid=False,
                    errors=errors,
                )
            )
        except Exception as exc:
            results.append(
                ValidationResult(
                    path=str(spec_path),
                    spec_type=spec_type,
                    valid=False,
                    errors=[str(exc)],
                )
            )

    return results
