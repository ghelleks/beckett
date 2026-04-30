"""RSS polling skill (r2e) — beckett-observe-rss."""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import os

from pydantic import BaseModel

from beckett.loop.deps import RoleDeps
from beckett.loop.phase_state import elapsed_minutes, save_phase_state
from beckett.loop.spec import GuardOutcome

log = logging.getLogger(__name__)

_RFEEDS = re.compile(r"(\d+)\s*(?:feed|feeds)", re.I)
_RITEMS = re.compile(r"(\d+)\s*(?:item|articles|messages|entries)", re.I)


class RssResult(BaseModel):
    feeds_polled: int = 0
    items_found: int = 0


async def observe_rss_guard(deps: RoleDeps) -> GuardOutcome:
    if not Path("~/.config/rss2email/config.cfg").expanduser().is_file():
        return GuardOutcome(triggered=False, detail="no rss2email config.cfg")
    if elapsed_minutes(deps.phase_state.last_observe_rss) < 90:
        ago = deps.phase_state.last_observe_rss
        return GuardOutcome(
            triggered=False,
            detail=f"RSS interval ({ago.isoformat(timespec='minutes') if ago else 'fresh'})",
        )
    return GuardOutcome(triggered=True, detail="RSS interval elapsed (≥90m) + rss2email config present")


async def observe_rss_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context  # runner contract
    env = dict(os.environ)
    feeds, items = 0, 0
    stdout = ""
    try:
        proc = subprocess.run(
            ["r2e", "run"],
            cwd=str(Path.home()),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        stdout = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        m = _RFEEDS.search(stdout)
        if m:
            feeds = int(m.group(1))
        m2 = _RITEMS.search(stdout)
        if m2:
            items = int(m2.group(1))
        lines = len([ln for ln in stdout.splitlines() if ln.strip()])
        if feeds == 0 and lines > 0:
            feeds = 1 if "error" not in stdout.lower() else feeds
            items = max(items, lines)
    except Exception as exc:
        log.warning("observe_rss_agent r2e failed role=%s: %s", deps.role, exc)

    deps.phase_state.last_observe_rss = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    result = RssResult(feeds_polled=feeds, items_found=items)
    return result.model_dump(mode="json")
