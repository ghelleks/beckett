"""Email classifier guard and agent."""

from __future__ import annotations

import subprocess

from beckett.loop.deps import RoleDeps
from beckett.loop.pai import maybe_run_pydantic_agent
from beckett.loop.spec import GuardOutcome


async def email_classifier_guard(deps: RoleDeps) -> GuardOutcome:
    gws_acc = deps.env.get("GWS_PROFILE", deps.role)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "triage", "--account", gws_acc],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            return GuardOutcome(triggered=True, detail=f"{lines} unread")
    except Exception:
        pass
    return GuardOutcome(triggered=False, detail="no unread")


async def email_classifier_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    ai = await maybe_run_pydantic_agent(
        deps,
        system_prompt="You classify unread inbox mail into reply_needed/review/todo/summarize.",
        prompt=f"Classify email backlog for role={deps.role}. Signal={guard.detail}",
    )
    return {"classified": 0, "skipped": 0, "detail": guard.detail, "ai": ai}
