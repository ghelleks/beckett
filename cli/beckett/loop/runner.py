"""Loop runner and CLI entry helpers."""

from __future__ import annotations

import asyncio
import json
import logging
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

log = logging.getLogger(__name__)


# ── Result models ─────────────────────────────────────────────────────────────


class SkillRunResult(BaseModel):
    id: str
    guard: GuardOutcome
    skipped: bool = False  # True when guard/agent not in registry (lenient mode)
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


# ── Helpers ───────────────────────────────────────────────────────────────────


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


def _guard_timeout(deps: RoleDeps) -> int:
    """Return guard subprocess timeout in seconds (closes GAP 7).

    Reads BECKETT_GUARD_TIMEOUT then MASKS_GUARD_TIMEOUT from deps.env.
    Default is 5 seconds (matching original run_cmd.py behavior).
    """
    for key in ("BECKETT_GUARD_TIMEOUT", "MASKS_GUARD_TIMEOUT"):
        raw = deps.env.get(key, "").strip()
        if raw:
            try:
                return max(1, int(raw))
            except ValueError:
                pass
    return 5


# ── Registry validation (lenient, GAP 6) ─────────────────────────────────────


def _validate_registry(spec: LoopSpec) -> set[str]:
    """Return the set of entry IDs that are missing from the registry.

    Logs a warning per missing entry instead of raising, matching the old
    run_cmd.py behavior where missing guards logged name:X and were skipped.
    """
    skipped: set[str] = set()
    for entry in spec.all_entries:
        guard_name = entry.guard or entry.id
        missing: list[str] = []
        if not has_guard(guard_name):
            missing.append(f"guard:{guard_name}")
        if not has_agent(entry.agent):
            missing.append(f"agent:{entry.agent}")
        if missing:
            log.warning(
                "loop entry %r skipped — not in registry: %s",
                entry.id,
                ", ".join(missing),
            )
            skipped.add(entry.id)
    return skipped


# ── Two-pass phase execution (GAP 3) ─────────────────────────────────────────


async def _run_phase(
    phase_name: str,
    entries: list[Any],
    deps: RoleDeps,
    context: dict[str, Any] | None,
    skipped_ids: set[str],
) -> tuple[PhaseRunResult, dict[str, Any]]:
    """Execute a single OODA phase with a two-pass guard→agent strategy.

    Pass 1: evaluate ALL guards first and build trigger_map.
    Pass 2: for each triggered entry (in order), run its agent with the full
            trigger_map in context so every agent knows what else fired.

    This restores cross-skill awareness within a phase (closes GAP 3).
    """
    phase = PhaseRunResult(phase=phase_name)
    next_context: dict[str, Any] = dict(context or {})

    # ── Pass 1: evaluate all guards ──────────────────────────────────────────
    trigger_map: dict[str, GuardOutcome] = {}
    for entry in entries:
        if entry.id in skipped_ids:
            phase.skills.append(SkillRunResult(
                id=entry.id,
                guard=GuardOutcome(triggered=False, detail="skipped:missing-registry"),
                skipped=True,
            ))
            continue
        guard_name = entry.guard or entry.id
        guard_fn = guard_for(guard_name)
        try:
            outcome = await guard_fn(deps)
        except Exception as exc:
            log.warning("Guard %r raised for role=%s: %s", guard_name, deps.role, exc)
            outcome = GuardOutcome(triggered=False, detail=f"guard-error:{exc}")
        trigger_map[entry.id] = outcome

    # Expose full phase trigger map so agents can see sibling outcomes
    next_context["_phase_triggers"] = {
        k: v.model_dump() for k, v in trigger_map.items()
    }

    # ── Pass 2: run agents for triggered entries in order ────────────────────
    for entry in entries:
        if entry.id in skipped_ids:
            continue  # already appended in pass 1
        guard = trigger_map.get(entry.id, GuardOutcome(triggered=False))
        skill_result = SkillRunResult(id=entry.id, guard=guard)
        if guard.triggered:
            agent_fn = agent_for(entry.agent)
            try:
                out = await agent_fn(deps, guard, context=next_context)
                skill_result.agent_result = out if isinstance(out, dict) else {"result": out}
                # Make this agent's output available to subsequent sibling agents
                next_context[entry.id] = skill_result.agent_result
            except Exception as exc:
                log.error(
                    "Agent %r raised for role=%s: %s", entry.agent, deps.role, exc
                )
                skill_result.error = str(exc)
        phase.skills.append(skill_result)

    return phase, next_context


# ── Cycle orchestration ───────────────────────────────────────────────────────


def run_loop_cycle(deps: RoleDeps, once: bool = False) -> LoopRunResult:
    register_builtin_skills()
    skipped_ids = _validate_registry(deps.loop_spec)  # lenient — returns skipped set

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
            phase, ctx = await _run_phase(phase_name, entries, deps, ctx, skipped_ids)
            result.phases.append(phase)

        result.triggered_count = sum(
            1
            for ph in result.phases
            for sk in ph.skills
            if sk.guard.triggered and not sk.skipped
        )
        result.success = all(
            sk.error is None for ph in result.phases for sk in ph.skills
        )

    asyncio.run(_run())
    result.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result.committed = commit_role_changes(
        deps.role_dir, f"loop: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    _write_last_run(deps.role_dir, result)
    return result


# ── Dry-run: guards only, no agents ──────────────────────────────────────────


async def _run_dryrun_phases(
    deps: RoleDeps,
    skipped_ids: set[str],
) -> list[PhaseRunResult]:
    """Evaluate all guards across all phases; return results without running agents."""
    phases: list[PhaseRunResult] = []
    for phase_name, entries in (
        ("observe", deps.loop_spec.observe.entries),
        ("orient", deps.loop_spec.orient.entries),
        ("act", deps.loop_spec.act.entries),
    ):
        phase = PhaseRunResult(phase=phase_name)
        for entry in entries:
            if entry.id in skipped_ids:
                phase.skills.append(SkillRunResult(
                    id=entry.id,
                    guard=GuardOutcome(triggered=False, detail="skipped:missing-registry"),
                    skipped=True,
                ))
                continue
            guard_name = entry.guard or entry.id
            guard_fn = guard_for(guard_name)
            try:
                outcome = await guard_fn(deps)
            except Exception as exc:
                log.warning("Guard %r raised: %s", guard_name, exc)
                outcome = GuardOutcome(triggered=False, detail=f"guard-error:{exc}")
            phase.skills.append(SkillRunResult(id=entry.id, guard=outcome))
        phases.append(phase)
    return phases


def run_loop_dryrun(deps: RoleDeps) -> LoopRunResult:
    """Evaluate all guards and print a trigger table. No agents are invoked.

    Useful for verifying guard logic without spending tokens.
    """
    register_builtin_skills()
    skipped_ids = _validate_registry(deps.loop_spec)

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = LoopRunResult(
        role=deps.role,
        started_at=started,
        finished_at=started,
        total_entries=len(deps.loop_spec.all_entries),
    )

    phases = asyncio.run(_run_dryrun_phases(deps, skipped_ids))
    result.phases = phases
    result.triggered_count = sum(
        1 for ph in phases for sk in ph.skills if sk.guard.triggered and not sk.skipped
    )
    result.success = True
    result.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result


# ── Single-skill invocation ───────────────────────────────────────────────────


async def _run_one_skill(
    deps: RoleDeps,
    entry: Any,
    *,
    force_trigger: bool,
    skipped_ids: set[str],
) -> SkillRunResult:
    if entry.id in skipped_ids:
        return SkillRunResult(
            id=entry.id,
            guard=GuardOutcome(triggered=False, detail="skipped:missing-registry"),
            skipped=True,
        )
    guard_name = entry.guard or entry.id
    guard_fn = guard_for(guard_name)
    try:
        outcome = await guard_fn(deps)
    except Exception as exc:
        outcome = GuardOutcome(triggered=False, detail=f"guard-error:{exc}")

    if force_trigger and not outcome.triggered:
        outcome = GuardOutcome(triggered=True, detail=f"forced (was: {outcome.detail})")

    skill_result = SkillRunResult(id=entry.id, guard=outcome)
    if outcome.triggered:
        agent_fn = agent_for(entry.agent)
        try:
            out = await agent_fn(deps, outcome, context={"_forced": force_trigger})
            skill_result.agent_result = out if isinstance(out, dict) else {"result": out}
        except Exception as exc:
            skill_result.error = str(exc)
    return skill_result


def run_single_skill(
    deps: RoleDeps,
    skill_id: str,
    *,
    force_trigger: bool = True,
) -> tuple[SkillRunResult, bool]:
    """Run guard + agent for a single skill entry by ID.

    Args:
        deps: Role dependencies.
        skill_id: The entry id from loop.yaml (e.g. 'ooda-observe').
        force_trigger: When True (default), run the agent even if the guard skips.

    Returns:
        (SkillRunResult, committed) where committed is True if a git commit was made.
    """
    register_builtin_skills()
    skipped_ids = _validate_registry(deps.loop_spec)

    entry = next(
        (e for e in deps.loop_spec.all_entries if e.id == skill_id),
        None,
    )
    if entry is None:
        known = [e.id for e in deps.loop_spec.all_entries]
        raise LoopConfigError(
            f"skill {skill_id!r} not found in LoopSpec. Known: {known}"
        )

    skill_result = asyncio.run(
        _run_one_skill(deps, entry, force_trigger=force_trigger, skipped_ids=skipped_ids)
    )
    committed = commit_role_changes(
        deps.role_dir,
        f"loop[skill={skill_id}]: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    return skill_result, committed


# ── CLI entry points ──────────────────────────────────────────────────────────


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
            f"success={'yes' if res.success else 'no'} "
            f"committed={'yes' if res.committed else 'no'}"
        )
    if fatal:
        raise typer.Exit(1)
    if partial:
        raise typer.Exit(2)


def run_loop_daemon(
    role_target: str | None = None, interval: str = "15m", spec_path: str | None = None
) -> None:
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
            pass
        if stop["value"]:
            break
        time.sleep(sleep_s)
