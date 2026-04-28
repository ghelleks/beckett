"""Orient synthesis guard and agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from beckett.loop.deps import RoleDeps
from beckett.loop.memory_tools import write_memory
from beckett.loop.pai import maybe_run_pydantic_agent
from beckett.loop.spec import GuardOutcome


def _recent_synthesis(log_path: Path, cutoff: datetime) -> bool:
    if not log_path.is_file():
        return False
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("SYNTHESIS "):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        raw = parts[1].replace("Z", "+00:00")
        try:
            ts = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts > cutoff:
            return True
    return False


async def orient_synthesis_guard(deps: RoleDeps) -> GuardOutcome:
    syn_day = int(deps.env.get("SYNTHESIS_DAY", "0"))  # 0 Sunday
    if int(datetime.now().strftime("%w")) != syn_day:
        return GuardOutcome(triggered=False, detail="wrong day")
    log = deps.personal_dir / ".synthesis.log"
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    if _recent_synthesis(log, cutoff):
        return GuardOutcome(triggered=False, detail="cooldown active")
    return GuardOutcome(triggered=True, detail="synthesis day")


async def orient_synthesis_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    ai = await maybe_run_pydantic_agent(
        deps,
        system_prompt="You are the Beckett orient synthesis agent. Summarize cross-role patterns.",
        prompt="Synthesize cross-role memory patterns.",
    )
    if deps.role != "personal":
        return {"patterns_found": 0, "written": 0, "stale_updated": 0, "detail": "requires personal role", "ai": ai}

    content = "\n".join(
        [
            "# Cross-role synthesis",
            "",
            "**Status:** current",
            "",
            "## Pattern",
            "",
            "Automated synthesis placeholder entry.",
            "",
            "## Evidence",
            "",
            f"- ({deps.role}) {datetime.now(timezone.utc).date()} — `Memory/` — loop-triggered synthesis",
        ]
    )
    write_memory(
        deps,
        "Synthesis/loop-synthesis-placeholder",
        content,
        allow_personal_synthesis=True,
    )
    log = deps.personal_dir / ".synthesis.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"SYNTHESIS {now} — 1 patterns found, 1 updated\n")
    return {"patterns_found": 1, "written": 1, "stale_updated": 0, "ai": ai}
