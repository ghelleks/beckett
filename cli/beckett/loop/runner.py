"""Loop runner and CLI entry helpers."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel, Field

from beckett.loop.deps import RoleDeps, build_role_deps
from beckett.loop.memory_tools import commit_role_changes
from beckett.loop.registry import agent_for, guard_for, has_agent, has_guard
from beckett.loop.skills import register_builtin_skills
from beckett.loop.spec import GuardOutcome, LoopConfigError, LoopSpec, as_jsonable
from beckett.paths import resolve_base_path
from beckett.roles import iter_role_dirs


class SkillRunResult(BaseModel):
    id: str
    guard: GuardOutcome
    agent_result: dict[str, Any] | None = None
    error: str | None = None


class PhaseRunResult(BaseModel):
    phase: str
    skills: list[SkillRunResult] = Field(default_factory=list)


class LoopRunResult(BaseModel):
    role: str
    started_at: str
    finished_at: str
    phases: list[PhaseRunResult] = Field(default_factory=list)
    triggered_count: int = 0
    total_entries: int = 0
    success: bool = True
    fatal: bool = False
    committed: bool = False


def _interval_seconds(raw: str) -> int:
    s = raw.strip().lower()
    if not s:
        return 900
    if s.endswith("ms"):
        return max(1, int(float(s[:-2]) / 1000))
    if s.endswith("s"):
        return max(1, int(float(s[:-1])))
    if s.endswith("m"):
        return max(1, int(float(s[:-1]) * 60))
    if s.endswith("h"):
        return max(1, int(float(s[:-1]) * 3600))
    return max(1, int(float(s)))


def _active_hours_allows(spec: LoopSpec) -> bool:
    if not spec.active_hours:
        return True
    # Lightweight parser: HH:MM-HH:MM TZ. If malformed, allow and rely on doctor/spec tests.
    try:
        window = spec.active_hours.split()[0]
        start_s, end_s = window.split("-", 1)
        sh, sm = [int(x) for x in start_s.split(":")]
        eh, em = [int(x) for x in end_s.split(":")]
        now = datetime.now()
        minutes = now.hour * 60 + now.minute
        start = sh * 60 + sm
        end = eh * 60 + em
        return start <= minutes <= end
    except Exception:
        return True


def _write_last_run(role_dir: Path, result: LoopRunResult) -> None:
    state_dir = role_dir / ".ooda-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    out = state_dir / "last-run.json"
    out.write_text(json.dumps(as_jsonable(result), indent=2), encoding="utf-8")


def _validate_registry(spec: LoopSpec) -> None:
    missing: list[str] = []
    for entry in spec.all_entries:
        guard_name = entry.guard or entry.id
        if not has_guard(guard_name):
            missing.append(f"guard:{guard_name}")
        if not has_agent(entry.agent):
            missing.append(f"agent:{entry.agent}")
    if missing:
        raise LoopConfigError(f"unregistered loop tools: {', '.join(sorted(set(missing)))}")


async def _run_phase(
    phase_name: str,
    entries: list[Any],
    deps: RoleDeps,
    context: dict[str, Any] | None,
) -> tuple[PhaseRunResult, dict[str, Any]]:
    phase = PhaseRunResult(phase=phase_name)
    next_context = dict(context or {})
    for entry in entries:
        guard_name = entry.guard or entry.id
        guard_fn = guard_for(guard_name)
        agent_fn = agent_for(entry.agent)
        guard = await guard_fn(deps)
        skill_result = SkillRunResult(id=entry.id, guard=guard)
        if guard.triggered:
            try:
                out = await agent_fn(deps, guard, context=next_context)
                skill_result.agent_result = out if isinstance(out, dict) else {"result": out}
                next_context[entry.id] = skill_result.agent_result
            except Exception as exc:  # pragma: no cover - runtime error path
                skill_result.error = str(exc)
        phase.skills.append(skill_result)
    return phase, next_context


def run_loop_cycle(deps: RoleDeps, once: bool = False) -> LoopRunResult:
    register_builtin_skills()
    _validate_registry(deps.loop_spec)

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = LoopRunResult(
        role=deps.role,
        started_at=started,
        finished_at=started,
        total_entries=len(deps.loop_spec.all_entries),
    )
    if (not once) and (not _active_hours_allows(deps.loop_spec)):
        result.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_last_run(deps.role_dir, result)
        return result

    async def _run() -> None:
        nonlocal result
        ctx: dict[str, Any] = {}
        for phase_name, entries in (
            ("observe", deps.loop_spec.observe.entries),
            ("orient", deps.loop_spec.orient.entries),
            ("act", deps.loop_spec.act.entries),
        ):
            phase, ctx = await _run_phase(phase_name, entries, deps, ctx)
            result.phases.append(phase)

        result.triggered_count = sum(
            1
            for ph in result.phases
            for sk in ph.skills
            if sk.guard.triggered
        )
        result.success = all(sk.error is None for ph in result.phases for sk in ph.skills)

    asyncio.run(_run())
    result.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result.committed = commit_role_changes(deps.role_dir, f"loop: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    _write_last_run(deps.role_dir, result)
    return result


def _collect_target_paths(role_target: str | None) -> list[str]:
    if role_target:
        return [role_target]
    return [str(p) for p in iter_role_dirs(resolve_base_path())]


def run_loop_once(role_target: str | None = None, spec_path: str | None = None) -> None:
    results = []
    fatal = False
    partial = False
    if spec_path and not role_target:
        typer.secho("`--spec` requires `--role-target`", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)

    for target in _collect_target_paths(role_target):
        role_name = Path(target).name
        try:
            deps = build_role_deps(target, explicit_spec=spec_path)
            res = run_loop_cycle(deps, once=True)
            results.append(res)
            partial = partial or (not res.success)
        except LoopConfigError as exc:
            fatal = True
            typer.secho(f"[FAIL] {role_name}: {exc}", err=True, fg=typer.colors.RED)
        except Exception as exc:
            fatal = True
            typer.secho(f"[FAIL] {role_name}: {exc}", err=True, fg=typer.colors.RED)

    for res in results:
        typer.echo(
            f"{res.role}: triggered={res.triggered_count}/{res.total_entries} "
            f"success={'yes' if res.success else 'no'} committed={'yes' if res.committed else 'no'}"
        )
    if fatal:
        raise typer.Exit(1)
    if partial:
        raise typer.Exit(2)


def run_loop_daemon(role_target: str | None = None, interval: str = "15m", spec_path: str | None = None) -> None:
    stop = {"value": False}

    def _sig_handler(_signum, _frame) -> None:
        stop["value"] = True

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    sleep_s = _interval_seconds(os.environ.get("BECKETT_LOOP_INTERVAL", interval))
    while not stop["value"]:
        try:
            run_loop_once(role_target=role_target, spec_path=spec_path)
        except typer.Exit:
            # daemon mode keeps running unless signaled
            pass
        if stop["value"]:
            break
        time.sleep(sleep_s)
