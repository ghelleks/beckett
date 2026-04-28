"""``beckett doctor`` — LoopSpec, registry, and model env readiness."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer

from beckett.loop.registry import has_agent, has_guard
from beckett.loop.skills import register_builtin_skills
from beckett.loop.spec import LoopConfigError, load_loop_spec
from beckett.paths import resolve_base_path
from beckett.role_path import resolve_role_dir
from beckett.roles import iter_role_dirs


def _collect_role_dirs(explicit: tuple[str, ...]) -> list[Path]:
    if explicit:
        return [resolve_role_dir(t) for t in explicit]
    return list(iter_role_dirs(resolve_base_path()))


def _has_model_env() -> bool:
    keys = [
        "BECKETT_MODEL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
    ]
    return any(os.environ.get(k) for k in keys)


def doctor_cmd(json_out: bool = False, role_targets: tuple[str, ...] = ()) -> None:
    """Validate LoopSpec files, registry coverage, and model env."""
    roles = _collect_role_dirs(role_targets)
    checks: list[dict[str, Any]] = []
    register_builtin_skills()

    def add(cid: str, ok: bool, msg: str, status: str | None = None) -> None:
        st = status or ("pass" if ok else "fail")
        checks.append({"id": cid, "status": st, "message": msg})

    bad_specs: list[str] = []
    specs_by_role: dict[str, Any] = {}
    for r in roles:
        try:
            specs_by_role[r.name] = load_loop_spec(r)
        except LoopConfigError as exc:
            bad_specs.append(f"{r.name}: {exc}")
    ok1 = not bad_specs
    msg1 = "all roles have valid loop specs" if ok1 else "; ".join(bad_specs)
    add("loop_spec", ok1, msg1)

    missing_registry: list[str] = []
    for role_name, spec in specs_by_role.items():
        for entry in spec.all_entries:
            guard_id = entry.guard or entry.id
            if not has_guard(guard_id):
                missing_registry.append(f"{role_name}: guard:{guard_id}")
            if not has_agent(entry.agent):
                missing_registry.append(f"{role_name}: agent:{entry.agent}")
    ok2 = not missing_registry
    msg2 = "all loop entries resolved by registry" if ok2 else "; ".join(sorted(missing_registry))
    add("registry", ok2, msg2)

    ok3 = _has_model_env()
    msg3 = "model env configured" if ok3 else "missing model env (set BECKETT_MODEL and/or provider API key)"
    add("model_env", ok3, msg3, status=("pass" if ok3 else "warn"))

    blocking_ok = all(c["status"] != "fail" for c in checks)

    if json_out:
        out = {"ok": blocking_ok, "checks": checks}
        typer.echo(json.dumps(out, indent=2))
    else:
        for c in checks:
            tag = c["status"].upper()
            typer.echo(f"[{tag}] {c['id']}: {c['message']}")

    if not blocking_ok:
        raise typer.Exit(1)
