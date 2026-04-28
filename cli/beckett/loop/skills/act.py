"""Act guard and agent."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from beckett.loop.deps import RoleDeps
from beckett.loop.memory_tools import write_memory
from beckett.loop.pai import maybe_run_pydantic_agent
from beckett.loop.spec import GuardOutcome


async def act_guard(deps: RoleDeps) -> GuardOutcome:
    try:
        proc = subprocess.run(
            ["td", "find-tasks", "--filter", "(today | overdue) & (@agent | @decision)"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            count = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            return GuardOutcome(triggered=True, detail=f"{count} actionable tasks")
    except Exception:
        pass
    return GuardOutcome(triggered=False, detail="no actionable tasks")


async def act_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    ai = await maybe_run_pydantic_agent(
        deps,
        system_prompt="You are the Beckett Act agent. Execute actionable tasks.",
        prompt=f"Execute act phase for role={deps.role}. Signal={guard.detail}",
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    content = "\n".join(["# Act Result", "", f"- Timestamp: {now}", f"- Detail: {guard.detail}"])
    sub = Path("Actions") / f"act-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    write_memory(deps, str(sub), content)
    return {"executed": 0, "failed": 0, "detail": guard.detail, "ai": ai}
