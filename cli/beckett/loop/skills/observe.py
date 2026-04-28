"""Observe skill guard and agent."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from beckett.loop.deps import RoleDeps
from beckett.loop.memory_tools import write_memory
from beckett.loop.pai import maybe_run_pydantic_agent
from beckett.loop.spec import GuardOutcome


async def observe_guard(deps: RoleDeps) -> GuardOutcome:
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

    marker = deps.role_dir / ".ooda-pending" / "observer.txt"
    if marker.is_file() and marker.read_text(encoding="utf-8", errors="replace").strip():
        return GuardOutcome(triggered=True, detail="observer marker")
    return GuardOutcome(triggered=False, detail="quiet")


async def observe_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    ai = await maybe_run_pydantic_agent(
        deps,
        system_prompt="You are the Beckett Observe agent. Return concise structured observations.",
        prompt=f"Observe role={deps.role}. Trigger={guard.detail}.",
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    content = "\n".join(
        [
            "# Observation",
            "",
            f"- Timestamp: {now}",
            f"- Role: {deps.role}",
            f"- Trigger detail: {guard.detail}",
        ]
    )
    sub = Path("Observations") / f"observe-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    write_memory(deps, str(sub), content)
    return {"observations": [guard.detail], "files_written": 1, "ai": ai}
