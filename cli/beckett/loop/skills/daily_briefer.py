"""Daily briefer guard and agent."""

from __future__ import annotations

from datetime import datetime

from beckett.loop.deps import RoleDeps
from beckett.loop.pai import maybe_run_pydantic_agent
from beckett.loop.spec import GuardOutcome


def _minutes_now() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


async def daily_briefer_guard(deps: RoleDeps) -> GuardOutcome:
    target_raw = deps.env.get("DAILY_BRIEFER_TARGET", "06:45")
    hh, mm = target_raw.split(":")
    target = int(hh) * 60 + int(mm)
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


async def daily_briefer_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    ai = await maybe_run_pydantic_agent(
        deps,
        system_prompt="You generate a concise daily briefing.",
        prompt=f"Generate daily briefing for role={deps.role}.",
    )
    return {"delivered": True, "detail": guard.detail, "ai": ai}
