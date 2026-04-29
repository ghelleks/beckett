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
    """Fetch unread inbox email summaries for this role's GWS account (JSON array)."""
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage", "--format", "json"],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        if proc.returncode == 0:
            raw = "\n".join(
                ln for ln in proc.stdout.splitlines() if not ln.startswith("Using")
            ).strip()
            return raw or "[]"
        return "[]"
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
            ["gws", "gmail", "+triage", "--format", "json"],
            capture_output=True, text=True, timeout=guard_timeout(deps), env=env,
        )
        if proc.returncode == 0:
            # Strip the "Using keyring backend" line before parsing JSON
            raw = "\n".join(
                ln for ln in proc.stdout.splitlines() if not ln.startswith("Using")
            ).strip()
            if raw:
                messages = json.loads(raw)
                count = len(messages)
                if count > 0:
                    return GuardOutcome(triggered=True, detail=f"{count} unread")
    except Exception:
        pass

    marker = deps.role_dir / ".ooda-pending" / "observer.txt"
    if marker.is_file() and marker.read_text(encoding="utf-8", errors="replace").strip():
        return GuardOutcome(triggered=True, detail="observer marker")
    return GuardOutcome(triggered=False, detail="quiet")


# ── Agent ─────────────────────────────────────────────────────────────────────


def _fetch_signals(deps: RoleDeps) -> dict:
    """Pre-fetch signal data via Python tools for the subprocess delegation path.

    Returns empty signals quickly when no GWS config is present (e.g. in tests).
    """
    env = gws_env(deps)
    timeout = guard_timeout(deps)
    # Skip gws calls when no real GWS config dir exists (test environments)
    config_dir = env.get("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", "")
    if not config_dir or not Path(config_dir).is_dir():
        marker_text = ""
        marker = deps.role_dir / ".ooda-pending" / "observer.txt"
        if marker.is_file():
            marker_text = marker.read_text(encoding="utf-8", errors="replace").strip()
        return {"emails": [], "marker": marker_text}

    # Emails
    emails: list[dict] = []
    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage", "--format", "json"],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        if proc.returncode == 0:
            raw = "\n".join(
                ln for ln in proc.stdout.splitlines() if not ln.startswith("Using")
            ).strip()
            if raw:
                parsed = json.loads(raw)
                emails = parsed if isinstance(parsed, list) else []
    except Exception:
        pass

    # Observer marker
    marker_text = ""
    marker = deps.role_dir / ".ooda-pending" / "observer.txt"
    if marker.is_file():
        marker_text = marker.read_text(encoding="utf-8", errors="replace").strip()

    return {"emails": emails, "marker": marker_text}


async def observe_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    phase_context = ""
    if context and context.get("_phase_triggers"):
        phase_context = f"\nPhase trigger context: {context['_phase_triggers']}"

    fallback: dict = {
        "signals_found": 1 if guard.triggered else 0,
        "files_written": 0,
        "sources": [guard.detail],
    }

    model = deps.env.get("BECKETT_MODEL", "").strip()
    llm_cmd = (deps.env.get("BECKETT_LLM_CMD") or deps.env.get("MASKS_LLM_CMD") or "").strip()

    if model:
        # Full Pydantic AI path — model orchestrates tool calls
        prompt = (
            f"Role: {deps.role}\n"
            f"Trigger: {guard.detail}{phase_context}\n\n"
            "Survey this role's incoming signals and write structured observations."
        )
        return await run_agent(_observe_agent, prompt, deps, fallback_result=fallback)

    if llm_cmd and guard.triggered:
        # Subprocess delegation path — pre-fetch signals in Python, ask claude
        # to generate observation text only (not perform agentic work).
        signals = _fetch_signals(deps)
        email_lines = "\n".join(
            f"  - {m.get('from', '?')} — {m.get('subject', '(no subject)')}"
            for m in signals["emails"][:10]
        ) or "  (none)"
        marker_line = f"Observer marker: {signals['marker']}" if signals["marker"] else ""

        prompt = (
            f"Role: {deps.role}\n"
            f"Trigger: {guard.detail}{phase_context}\n\n"
            f"Unread emails ({len(signals['emails'])}):\n{email_lines}\n"
            + (f"{marker_line}\n" if marker_line else "")
            + "\nWrite a concise structured observation note (3-8 bullet points) "
            "summarising what signals are present and what they suggest about "
            "priorities or attention needed. Use markdown. Do not call any tools."
        )

        from beckett.loop.claude import invoke_claude
        from beckett.loop.memory_tools import write_memory

        now = datetime.now(timezone.utc)
        try:
            output = invoke_claude(deps, prompt)
            content = output.strip() or (
                f"# Observation\n\n- Trigger: {guard.detail}\n"
                f"- Emails: {len(signals['emails'])} unread\n"
            )
        except Exception:
            content = (
                f"# Observation\n\n- Trigger: {guard.detail}\n"
                f"- Emails: {len(signals['emails'])} unread\n"
            )

        sub = Path("Observations") / now.strftime("%Y%m%d-%H%M%S")
        try:
            write_memory(deps, str(sub), content)
            return {"signals_found": len(signals["emails"]) + bool(signals["marker"]),
                    "files_written": 1, "sources": [guard.detail]}
        except Exception:
            return fallback

    # No model and no LLM cmd — write minimal stub
    if guard.triggered:
        from beckett.loop.memory_tools import write_memory

        now = datetime.now(timezone.utc)
        content = f"# Observation\n\n- Timestamp: {now.isoformat(timespec='seconds')}\n- Trigger: {guard.detail}\n"
        sub = Path("Observations") / now.strftime("%Y%m%d-%H%M%S")
        try:
            write_memory(deps, str(sub), content)
            return {**fallback, "files_written": 1}
        except Exception:
            pass

    return fallback
