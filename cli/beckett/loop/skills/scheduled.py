"""Scheduled act-phase jobs — staff update, efficiency CSV, desktop archive."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from beckett.loop.claude import invoke_claude_agent
from beckett.loop.deps import RoleDeps
from beckett.loop.phase_state import elapsed_minutes, save_phase_state
from beckett.loop.spec import GuardOutcome

log = logging.getLogger(__name__)


class ScheduledResult(BaseModel):
    completed: bool
    detail: str


def _efficiency_log_csv_path() -> Path:
    return Path("~/.looper/efficiency-log.csv").expanduser()


def _efficiency_log_written_today() -> bool:
    p = _efficiency_log_csv_path()
    if not p.is_file():
        return False
    now = datetime.now(timezone.utc)
    mt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return mt.date() == now.date()


def _resolve_efficiency_script(deps: RoleDeps) -> Path | None:
    v = deps.env.get("BECKETT_EFFICIENCY_LOG_SCRIPT", "").strip()
    if v:
        cand = Path(v).expanduser()
        if cand.is_file():
            return cand
    root = deps.env.get("AGENT_SKILLS_ROOT", "").strip()
    if root:
        script = Path(root).expanduser() / "scripts" / "efficiency-log.py"
        if script.is_file():
            return script
    fb = Path.home() / "Code" / "agent-skills" / "scripts" / "efficiency-log.py"
    return fb if fb.is_file() else None


async def scheduled_staff_update_draft_guard(deps: RoleDeps) -> GuardOutcome:
    now = datetime.utcnow()
    if now.weekday() != 4:
        return GuardOutcome(triggered=False, detail="staff update: not Friday (UTC)")
    if elapsed_minutes(deps.phase_state.last_scheduled_staff_update) < 7 * 24 * 60:
        return GuardOutcome(triggered=False, detail="staff update: within 7d window")
    return GuardOutcome(triggered=True, detail="Friday UTC and staff-update interval elapsed")


async def scheduled_staff_update_draft_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    prompt = (
        f"Role: {deps.role}\nDraft the weekly staff leadership email using /weekly-staff-update. "
        "Return JSON {{\"done\": true}} when complete."
    )
    raw = invoke_claude_agent("beckett-scheduled-staff-update-draft", prompt, deps)
    ok = bool(raw and len(raw.strip()) > 30)
    deps.phase_state.last_scheduled_staff_update = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return ScheduledResult(
        completed=ok,
        detail="staff update draft invoked",
    ).model_dump(mode="json")


async def scheduled_efficiency_log_guard(deps: RoleDeps) -> GuardOutcome:
    if datetime.utcnow().weekday() >= 5:
        return GuardOutcome(triggered=False, detail="efficiency-log: weekend (UTC)")
    if elapsed_minutes(deps.phase_state.last_scheduled_efficiency_log) < 24 * 60:
        return GuardOutcome(triggered=False, detail="efficiency-log: <24h since last")
    return GuardOutcome(triggered=True, detail="weekday UTC; efficiency-log interval elapsed")


async def scheduled_efficiency_log_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    script = _resolve_efficiency_script(deps)
    if script is None:
        return ScheduledResult(
            completed=False,
            detail="BECKETT_EFFICIENCY_LOG_SCRIPT or ~/Code/agent-skills/scripts/efficiency-log.py not found",
        ).model_dump(mode="json")
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(script.parent.parent),
            capture_output=True,
            text=True,
            timeout=600,
            env=dict(os.environ),
        )
        ok = proc.returncode == 0
        detail = (proc.stderr or proc.stdout or "")[:500]
        if not ok:
            log.warning(
                "efficiency-log.py exit %s role=%s: %s", proc.returncode, deps.role, detail
            )
    except Exception as exc:
        ok = False
        detail = str(exc)
        log.warning("efficiency-log invocation failed role=%s: %s", deps.role, exc)

    deps.phase_state.last_scheduled_efficiency_log = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return ScheduledResult(completed=ok, detail=detail or "efficiency-log run").model_dump(mode="json")


async def scheduled_efficiency_email_guard(deps: RoleDeps) -> GuardOutcome:
    if datetime.utcnow().weekday() >= 5:
        return GuardOutcome(triggered=False, detail="efficiency-email: weekend (UTC)")
    if elapsed_minutes(deps.phase_state.last_scheduled_efficiency_email) < 24 * 60:
        return GuardOutcome(triggered=False, detail="efficiency-email: <24h since last")
    if not _efficiency_log_written_today():
        return GuardOutcome(
            triggered=False,
            detail="efficiency-email: log CSV not updated today",
        )
    return GuardOutcome(triggered=True, detail="weekday, interval, log fresh today")


async def scheduled_efficiency_email_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    script = _resolve_efficiency_script(deps)
    to_addr = deps.env.get("BECKETT_WORK_EMAIL", "").strip()
    if script is None or not to_addr:
        return ScheduledResult(
            completed=False,
            detail="missing efficiency script or BECKETT_WORK_EMAIL",
        ).model_dump(mode="json")
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--email", to_addr, "--days", "7"],
            cwd=str(script.parent.parent),
            capture_output=True,
            text=True,
            timeout=600,
            env=dict(os.environ),
        )
        ok = proc.returncode == 0
        detail = (proc.stderr or proc.stdout or "")[:500]
    except Exception as exc:
        ok, detail = False, str(exc)

    deps.phase_state.last_scheduled_efficiency_email = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return ScheduledResult(completed=ok, detail=detail or "efficiency email sent").model_dump(mode="json")


async def scheduled_desktop_archive_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_scheduled_desktop_archive) < 24 * 60:
        return GuardOutcome(triggered=False, detail="desktop-archive: <24h since last")
    return GuardOutcome(triggered=True, detail="desktop-archive interval elapsed")


async def scheduled_desktop_archive_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    prompt = (
        f"Role: {deps.role}\nRun desktop-archive for stale task folders per /desktop-archive skill. "
        "Return JSON {{\"done\": true}} when complete."
    )
    raw = invoke_claude_agent("beckett-scheduled-desktop-archive", prompt, deps)
    ok = bool(raw and len(raw.strip()) > 20)
    deps.phase_state.last_scheduled_desktop_archive = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return ScheduledResult(
        completed=ok,
        detail="desktop archive agent completed",
    ).model_dump(mode="json")
