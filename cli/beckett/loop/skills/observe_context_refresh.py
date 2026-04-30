"""Context refresh phase — beckett-observe-context-refresh."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from pydantic import BaseModel

from beckett.loop.claude import invoke_claude_agent
from beckett.loop.deps import RoleDeps
from beckett.loop.phase_state import elapsed_minutes, save_phase_state
from beckett.loop.spec import GuardOutcome

_JSON_OBJ = re.compile(r"\{[^{}]*\}")


class ContextRefreshResult(BaseModel):
    files_reviewed: int = 0
    updated: int = 0


async def observe_context_refresh_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_observe_context_refresh) < 72 * 60:
        return GuardOutcome(triggered=False, detail="context refresh interval <72h")
    return GuardOutcome(triggered=True, detail="context refresh interval elapsed (≥72h)")


def _parse_refresh_counts(raw: str) -> tuple[int, int]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            fr = data.get("files_reviewed") or data.get("reviewed") or 0
            return int(fr or 0), int(data.get("updated") or 0)
    except json.JSONDecodeError:
        pass
    for m in _JSON_OBJ.finditer(raw):
        try:
            data = json.loads(m.group())
            if isinstance(data, dict):
                fr = data.get("files_reviewed") or data.get("reviewed") or 0
                return int(fr or 0), int(data.get("updated") or 0)
        except json.JSONDecodeError:
            continue
    return 0, 0


async def observe_context_refresh_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    prompt = (
        f"Role: {deps.role}\nRun the observe context refresh cycle: refresh pod charters "
        "and core persona memory per plugin skills.\nRespond with JSON only: "
        '{"files_reviewed": <int>, "updated": <int>}'
    )
    raw = invoke_claude_agent("beckett-observe-context-refresh", prompt, deps)
    fr, upd = _parse_refresh_counts(raw)
    deps.phase_state.last_observe_context_refresh = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return ContextRefreshResult(files_reviewed=fr, updated=upd).model_dump(mode="json")
