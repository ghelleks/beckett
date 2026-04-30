"""Reply-needed hygiene — beckett-orient-hygiene."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from pydantic import BaseModel

from beckett.loop.claude import invoke_claude_agent
from beckett.loop.deps import RoleDeps
from beckett.loop.gws_util import gws_env
from beckett.loop.phase_state import elapsed_minutes, save_phase_state
from beckett.loop.preflight import GmailClient
from beckett.loop.spec import GuardOutcome

log = logging.getLogger(__name__)

_JSON_OBJ = re.compile(r"\{[^{}]*\}")


class HygieneResult(BaseModel):
    threads_reviewed: int = 0
    actions_taken: int = 0


def _parse_pair(raw: str) -> tuple[int, int]:
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            return (
                int(d.get("threads_reviewed") or d.get("reviewed") or 0),
                int(d.get("actions_taken") or d.get("actions") or 0),
            )
    except json.JSONDecodeError:
        pass
    for m in _JSON_OBJ.finditer(raw):
        try:
            d = json.loads(m.group())
            if isinstance(d, dict):
                return (
                    int(d.get("threads_reviewed") or d.get("reviewed") or 0),
                    int(d.get("actions_taken") or d.get("actions") or 0),
                )
        except json.JSONDecodeError:
            continue
    return 0, 0


async def orient_hygiene_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_orient_hygiene) < 20:
        return GuardOutcome(triggered=False, detail="hygiene interval <20m")
    if not GmailClient(gws_env(deps)).has_label("reply_needed"):
        return GuardOutcome(triggered=False, detail="no reply_needed labeled mail")
    return GuardOutcome(triggered=True, detail="reply_needed present; interval elapsed")


async def orient_hygiene_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    prompt = (
        f"Role: {deps.role}\nReview reply_needed Gmail threads; archive noise, escalate "
        "stale waits. Respond JSON only: {{\"threads_reviewed\": N, \"actions_taken\": N}}"
    )
    raw = invoke_claude_agent("beckett-orient-hygiene", prompt, deps)
    tr, tc = _parse_pair(raw)
    deps.phase_state.last_orient_hygiene = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return HygieneResult(threads_reviewed=tr, actions_taken=tc).model_dump(mode="json")
