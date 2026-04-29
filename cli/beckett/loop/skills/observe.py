"""Observe skill — guard and agent."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
from beckett.loop.gws_util import guard_timeout, gws_env
from beckett.loop.skill_agent import build_skill_agent, run_agent
from beckett.loop.spec import GuardOutcome

# ── Output type ───────────────────────────────────────────────────────────────


class ObserveResult(BaseModel):
    signals_found: int = 0
    files_written: int = 0
    sources: list[str] = []


# ── Pydantic AI agent ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the Beckett Observe agent for a Pirandello role.

Survey incoming signals (email, calendar, memory markers), decide which are worth
recording as structured observations, draft concise observation entries, and write
them to the role's Memory/Observations/ directory.

Steps:
1. Call get_unread_emails to fetch the inbox signal.
2. Call get_recent_calendar_events to fetch upcoming events.
3. Call get_observer_marker to read any pending observer note; call
   clear_observer_marker after reading it.
4. Draft factual, actionable observations. Skip noise.
5. Call write_memory_file for each observation (subpath like 'Observations/YYYYMMDD-HHmmss').
6. Return ObserveResult with signals_found, files_written, and sources.
"""

_observe_agent: Agent = build_skill_agent(
    system_prompt=_SYSTEM_PROMPT,
    output_type=ObserveResult,
)


@_observe_agent.tool
async def get_unread_emails(ctx: RunContext[RoleDeps]) -> str:
    """Fetch unread inbox email summaries for this role's GWS account."""
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage"],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return proc.stdout.strip() or "(no unread emails)"
    except Exception as exc:
        return f"(error fetching emails: {exc})"


@_observe_agent.tool
async def get_recent_calendar_events(ctx: RunContext[RoleDeps], hours: int = 4) -> str:
    """Fetch calendar events in the next N hours for this role's GWS account."""
    from datetime import timedelta
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    now = datetime.now(timezone.utc)
    time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    time_max = (now + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = json.dumps({
        "calendarId": "primary",
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 10,
    })
    try:
        proc = subprocess.run(
            ["gws", "calendar", "events", "list", "--params", params],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return proc.stdout.strip() or "(no upcoming events)"
    except Exception as exc:
        return f"(error fetching calendar: {exc})"


@_observe_agent.tool
async def get_observer_marker(ctx: RunContext[RoleDeps]) -> str:
    """Read the .ooda-pending/observer.txt marker file if present."""
    marker = ctx.deps.role_dir / ".ooda-pending" / "observer.txt"
    return marker.read_text(encoding="utf-8", errors="replace").strip() if marker.is_file() else ""


@_observe_agent.tool
async def clear_observer_marker(ctx: RunContext[RoleDeps]) -> str:
    """Delete the .ooda-pending/observer.txt marker after processing."""
    marker = ctx.deps.role_dir / ".ooda-pending" / "observer.txt"
    if marker.is_file():
        marker.unlink()
        return "marker cleared"
    return "no marker present"


# ── Guard ─────────────────────────────────────────────────────────────────────


async def observe_guard(deps: RoleDeps) -> GuardOutcome:
    """Trigger if there are unread emails or a pending observer marker."""
    env = gws_env(deps)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage"],
            capture_output=True, text=True, timeout=guard_timeout(deps), env=env,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            # gws +triage always prints a header line; subtract 1 for actual messages
            count = max(0, lines - 1)
            if count > 0:
                return GuardOutcome(triggered=True, detail=f"{count} unread")
    except Exception:
        pass

    marker = deps.role_dir / ".ooda-pending" / "observer.txt"
    if marker.is_file() and marker.read_text(encoding="utf-8", errors="replace").strip():
        return GuardOutcome(triggered=True, detail="observer marker")
    return GuardOutcome(triggered=False, detail="quiet")


# ── Agent ─────────────────────────────────────────────────────────────────────


async def observe_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    phase_context = ""
    if context and context.get("_phase_triggers"):
        phase_context = f"\nPhase trigger context: {context['_phase_triggers']}"

    prompt = (
        f"Role: {deps.role}\n"
        f"Trigger: {guard.detail}{phase_context}\n\n"
        "Survey this role's incoming signals and write structured observations."
    )

    fallback: dict = {
        "signals_found": 1 if guard.triggered else 0,
        "files_written": 0,
        "sources": [guard.detail],
    }

    result = await run_agent(_observe_agent, prompt, deps, fallback_result=fallback)

    if not deps.env.get("BECKETT_MODEL", "").strip() and guard.triggered:
        from beckett.loop.memory_tools import write_memory

        now = datetime.now(timezone.utc)
        content = "\n".join([
            "# Observation",
            "",
            f"- Timestamp: {now.isoformat(timespec='seconds')}",
            f"- Role: {deps.role}",
            f"- Trigger: {guard.detail}",
        ])
        sub = Path("Observations") / now.strftime("%Y%m%d-%H%M%S")
        try:
            write_memory(deps, str(sub), content)
            result = {**result, "files_written": result.get("files_written", 0) + 1}
        except Exception:
            pass

    return result
