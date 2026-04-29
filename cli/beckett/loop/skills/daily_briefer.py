"""Daily briefer skill — guard and agent."""

from __future__ import annotations

import subprocess
from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
from beckett.loop.skill_agent import build_skill_agent, run_agent
from beckett.loop.spec import GuardOutcome

# ── Output type ───────────────────────────────────────────────────────────────


class BriefingResult(BaseModel):
    delivered: bool = False
    sections: list[str] = []


# ── Pydantic AI agent ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the Beckett daily briefer for a Pirandello role.

Your job is to generate a concise daily briefing by gathering data from calendar,
tasks, and email, then delegating delivery to Claude via run_claude_skill.

Steps:
1. Call get_todays_calendar to see today's meetings and events.
2. Call get_todoist_tasks to see overdue and today's tasks.
3. Call get_unread_count to gauge inbox signal.
4. Call search_memory for recent relevant observations.
5. Synthesize a structured briefing with sections: Calendar, Tasks, Email Signal.
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
    gws_acc = ctx.deps.env.get("GWS_PROFILE", ctx.deps.role)
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["gws", "calendar", "events", "list", "--account", gws_acc,
             "--today", "--max-results", "20"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip() or "(no events today)"
    except Exception as exc:
        return f"(error: {exc})"


@_briefer_agent.tool
async def get_todoist_tasks(ctx: RunContext[RoleDeps], filter_expr: str = "today|overdue") -> str:
    """Fetch Todoist tasks matching filter (default: today and overdue)."""
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["td", "find-tasks", "--filter", filter_expr],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip() or "(no tasks)"
    except Exception as exc:
        return f"(error: {exc})"


@_briefer_agent.tool
async def get_unread_count(ctx: RunContext[RoleDeps]) -> str:
    """Return the number of unread inbox emails as a signal."""
    gws_acc = ctx.deps.env.get("GWS_PROFILE", ctx.deps.role)
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["gws", "gmail", "triage", "--account", gws_acc],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            n = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            return str(n)
        return "0"
    except Exception:
        return "unknown"


# ── Guard ─────────────────────────────────────────────────────────────────────


def _minutes_now() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


def _guard_timeout(deps: RoleDeps) -> int:
    try:
        return max(1, int(deps.env.get("BECKETT_GUARD_TIMEOUT") or deps.env.get("MASKS_GUARD_TIMEOUT") or 5))
    except (ValueError, TypeError):
        return 5


async def daily_briefer_guard(deps: RoleDeps) -> GuardOutcome:
    """Trigger once daily within ±15 minutes of DAILY_BRIEFER_TARGET (default 06:45)."""
    target_raw = deps.env.get("DAILY_BRIEFER_TARGET", "06:45")
    try:
        hh, mm = target_raw.split(":")
        target = int(hh) * 60 + int(mm)
    except Exception:
        target = 6 * 60 + 45

    delta = abs(_minutes_now() - target)
    if delta > 15:
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
    """Run the daily briefer agent.

    Content generation uses Pydantic AI tools (calendar, tasks, email count).
    Delivery delegates to Claude via run_claude_skill (Rule 6 — delivery may need MCP).
    Stamp file write (Rule 7) happens in the guard, not here.
    """
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
