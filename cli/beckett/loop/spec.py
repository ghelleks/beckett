"""LoopSpec models and loading helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LoopConfigError(RuntimeError):
    """Raised when a role has no valid LoopSpec."""


class GuardOutcome(BaseModel):
    triggered: bool
    detail: str = ""


class PhaseEntry(BaseModel):
    id: str
    guard: str | None = None
    agent: str


class Phase(BaseModel):
    entries: list[PhaseEntry] = Field(default_factory=list)


class LoopSpec(BaseModel):
    observe: Phase = Field(default_factory=Phase)
    orient: Phase = Field(default_factory=Phase)
    act: Phase = Field(default_factory=Phase)
    active_hours: str | None = None
    interval_minutes: int = 15

    @property
    def all_entries(self) -> list[PhaseEntry]:
        return [*self.observe.entries, *self.orient.entries, *self.act.entries]


def _load_py_spec(path: Path) -> LoopSpec:
    spec = importlib.util.spec_from_file_location("_beckett_loop_spec", str(path))
    if spec is None or spec.loader is None:
        raise LoopConfigError(f"unable to load python LoopSpec module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "LOOP_SPEC"):
        raise LoopConfigError(f"python LoopSpec file missing LOOP_SPEC: {path}")
    value = getattr(module, "LOOP_SPEC")
    if isinstance(value, LoopSpec):
        return value
    if isinstance(value, dict):
        return LoopSpec.model_validate(value)
    raise LoopConfigError(f"LOOP_SPEC must be LoopSpec or dict in: {path}")


def _load_data_spec(path: Path) -> LoopSpec:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return LoopSpec.model_validate(raw)
    if suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LoopSpec.model_validate(raw)
    if suffix == ".py":
        return _load_py_spec(path)
    raise LoopConfigError(f"unsupported LoopSpec file extension: {path}")


def _candidate_specs(role_dir: Path) -> list[Path]:
    return [
        role_dir / "loop.yaml",
        role_dir / "loop.yml",
        role_dir / "loop.json",
        role_dir / "loop.py",
    ]


def detect_spec_source(role_dir: Path, explicit_spec: Path | None = None) -> tuple[str, Path | None]:
    """Return a source status for roles command."""
    if explicit_spec is not None and explicit_spec.is_file():
        return explicit_spec.name, explicit_spec
    for cand in _candidate_specs(role_dir):
        if cand.is_file():
            return cand.name, cand
    if (role_dir / "OODA.md").is_file():
        return "OODA.md (unsupported)", role_dir / "OODA.md"
    return "missing", None


def load_loop_spec(role_dir: Path, explicit_spec: str | None = None) -> LoopSpec:
    """Load LoopSpec using precedence: explicit path > loop.yaml/json/py."""
    source: Path | None = None
    if explicit_spec:
        source = Path(explicit_spec).expanduser().resolve()
        if not source.is_file():
            raise LoopConfigError(f"explicit LoopSpec not found: {source}")
    else:
        for cand in _candidate_specs(role_dir):
            if cand.is_file():
                source = cand
                break

    if source is None:
        if (role_dir / "OODA.md").is_file():
            raise LoopConfigError(
                f"OODA.md is unsupported for loop runtime; create loop.yaml/json/py in {role_dir}"
            )
        raise LoopConfigError(f"no LoopSpec found in role directory: {role_dir}")

    try:
        return _load_data_spec(source)
    except Exception as exc:  # pragma: no cover - wrapped with source context
        raise LoopConfigError(f"invalid LoopSpec at {source}: {exc}") from exc


def as_jsonable(model: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(model, BaseModel):
        return model.model_dump(mode="json")
    return dict(model)
