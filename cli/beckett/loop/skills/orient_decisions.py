"""Orient decisions synthesis — beckett-orient-decisions."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from beckett.loop.claude import invoke_claude_agent
from beckett.loop.deps import RoleDeps
from beckett.loop.phase_state import elapsed_minutes, save_phase_state
from beckett.loop.spec import GuardOutcome

log = logging.getLogger(__name__)

_JSON_OBJ = re.compile(r"\{[^{}]*\}")


class DecisionsResult(BaseModel):
    decisions_synthesized: int = 0
    written: int = 0


def _new_observations_since(deps: RoleDeps, since: datetime | None) -> bool:
    obs_dir = deps.role_dir / "Memory" / "Observations"
    if not obs_dir.is_dir():
        return False
    ref_ts = datetime.min.replace(tzinfo=timezone.utc)
    if since is not None:
        ref_ts = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
    for path in obs_dir.iterdir():
        if not path.is_file():
            continue
        try:
            mt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mt > ref_ts:
            return True
    return False


async def orient_decisions_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_orient_decisions) < 30:
        return GuardOutcome(triggered=False, detail="orient-decisions interval <30m")
    ts = deps.phase_state.last_orient_decisions
    if not _new_observations_since(deps, ts):
        return GuardOutcome(triggered=False, detail="no new Memory/Observations since last run")
    return GuardOutcome(triggered=True, detail="interval ≥30m and new observations on disk")


def _parse_counts(raw: str) -> tuple[int, int]:
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            return int(d.get("decisions_synthesized") or d.get("synthesized") or 0), int(
                d.get("written") or 0
            )
    except json.JSONDecodeError:
        pass
    for m in _JSON_OBJ.finditer(raw):
        try:
            d = json.loads(m.group())
            if isinstance(d, dict):
                return int(d.get("decisions_synthesized") or d.get("synthesized") or 0), int(
                    d.get("written") or 0
                )
        except json.JSONDecodeError:
            continue
    return 0, 0


async def orient_decisions_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    prompt = (
        f"Role: {deps.role}\nSynthesize actionable decisions from latest observations in Memory/. "
        f"Persist to Memory/. "
        '{"decisions_synthesized": N, "written": N} as JSON.'
    )
    raw = invoke_claude_agent("beckett-orient-decisions", prompt, deps)
    syn, wr = _parse_counts(raw)
    deps.phase_state.last_orient_decisions = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return DecisionsResult(decisions_synthesized=syn, written=wr).model_dump(mode="json")
