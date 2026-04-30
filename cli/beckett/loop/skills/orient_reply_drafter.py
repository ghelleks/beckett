"""Reply drafter — beckett-orient-reply-drafter."""

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


class ReplyDraftResult(BaseModel):
    drafts_created: int = 0


def _drafts_from(raw: str) -> int:
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            return int(d.get("drafts_created") or d.get("drafts") or 0)
        if isinstance(d, list):
            return len(d)
    except json.JSONDecodeError:
        pass
    for m in _JSON_OBJ.finditer(raw):
        try:
            d = json.loads(m.group())
            if isinstance(d, dict):
                return int(d.get("drafts_created") or d.get("drafts") or 0)
        except json.JSONDecodeError:
            continue
    return 0


async def orient_reply_drafter_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_orient_reply_drafter) < 15:
        return GuardOutcome(triggered=False, detail="reply-drafter interval <15m")
    if deps.phase_state.last_orient_email is None:
        return GuardOutcome(triggered=False, detail="orient-email has not completed yet")
    if not GmailClient(gws_env(deps)).has_label("reply_needed"):
        return GuardOutcome(triggered=False, detail="no reply_needed mail")
    return GuardOutcome(triggered=True, detail="post-email + reply_needed; interval elapsed")


async def orient_reply_drafter_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    prompt = (
        f"Role: {deps.role}\nDraft replies per /beckett-email-reply-drafter for reply_needed inbox. "
        'JSON only: {"drafts_created": N}'
    )
    raw = invoke_claude_agent("beckett-orient-reply-drafter", prompt, deps)
    n = _drafts_from(raw)
    deps.phase_state.last_orient_reply_drafter = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return ReplyDraftResult(drafts_created=n).model_dump(mode="json")
