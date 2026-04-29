"""Daily briefer skill — guard and agent."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
from beckett.loop.gws_util import guard_timeout, gws_env
from beckett.loop.skill_agent import build_skill_agent, run_agent
from beckett.loop.spec import GuardOutcome

# ── Output type ───────────────────────────────────────────────────────────────


class BriefingResult(BaseModel):
    delivered: bool = False
    sections: list[str] = []


# ── Pydantic AI agent ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the Beckett daily briefer for a Pirandello role.

Generate a concise daily briefing by gathering data from calendar, tasks, and email,
then delegating delivery to Claude via run_claude_skill.

Steps:
1. Call get_todays_calendar to see today's meetings and events.
2. Call get_todoist_tasks to see overdue and today's tasks.
3. Call get_unread_count to gauge inbox signal.
4. Call search_memory for recent relevant observations.
5. Synthesize a briefing with sections: Calendar, Tasks, Email Signal.
6. Call run_claude_skill('daily-briefer-deliver', briefing_text) to deliver it.

Return BriefingResult with delivered=True and the list of section names produced.
"""

_briefer_agent: Agent = build_skill_agent(
    system_prompt=_SYSTEM_PROMPT,
    output_type=BriefingResult,
)


@_briefer_agent.tool
async def get_todays_calendar(ctx: RunContext[RoleDeps]) -> str:
    """Fetch today's calendar events for this role's GWS account."""
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    now = datetime.now(timezone.utc)
    end_of_day = now.replace(hour=23, minute=59, second=59)
    params = json.dumps({
        "calendarId": "primary",
        "timeMin": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timeMax": end_of_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 20,
    })
    try:
        proc = subprocess.run(
            ["gws", "calendar", "events", "list", "--params", params],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return proc.stdout.strip() or "(no events today)"
    except Exception as exc:
        return f"(error: {exc})"


@_briefer_agent.tool
async def get_todoist_tasks(ctx: RunContext[RoleDeps], filter_expr: str = "today|overdue") -> str:
    """Fetch Todoist tasks matching filter (default: today and overdue)."""
    timeout = guard_timeout(ctx.deps)
    try:
        proc = subprocess.run(
            ["td", "find-tasks", "--filter", filter_expr],
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.stdout.strip() or "(no tasks)"
    except Exception as exc:
        return f"(error: {exc})"


@_briefer_agent.tool
async def get_unread_count(ctx: RunContext[RoleDeps]) -> str:
    """Return the number of unread inbox emails as a signal."""
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage"],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            count = max(0, lines - 1)
            return str(count)
        return "0"
    except Exception:
        return "unknown"


# ── Guard ─────────────────────────────────────────────────────────────────────


def _minutes_now() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


async def daily_briefer_guard(deps: RoleDeps) -> GuardOutcome:
    """Trigger once daily within ±15 minutes of DAILY_BRIEFER_TARGET (default 06:45)."""
    target_raw = deps.env.get("DAILY_BRIEFER_TARGET", "06:45")
    try:
        hh, mm = target_raw.split(":")
        target = int(hh) * 60 + int(mm)
    except Exception:
        target = 6 * 60 + 45

    if abs(_minutes_now() - target) > 15:
        return GuardOutcome(triggered=False, detail=f"outside window ±15m at {target_raw}")

    stamp_dir = deps.role_dir / ".ooda-state"
    stamp_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp_dir / f"daily-briefer-{datetime.now().strftime('%Y-%m-%d')}"
    if stamp.exists():
        return GuardOutcome(triggered=False, detail="already ran today")
    stamp.write_text("1\n", encoding="utf-8")
    return GuardOutcome(triggered=True, detail="in window")


# ── Agent ─────────────────────────────────────────────────────────────────────


async def daily_briefer_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    phase_context = ""
    if context and context.get("_phase_triggers"):
        phase_context = f"\nPhase trigger context: {context['_phase_triggers']}"

    prompt = (
        f"Role: {deps.role}\n"
        f"Trigger: {guard.detail}{phase_context}\n\n"
        "Generate and deliver the daily briefing for this role."
    )

    fallback: dict = {"delivered": True, "sections": []}
    return await run_agent(_briefer_agent, prompt, deps, fallback_result=fallback)
