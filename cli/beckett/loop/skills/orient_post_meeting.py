"""Post-meeting follow-up — beckett-orient-post-meeting."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from pydantic import BaseModel

from beckett.loop.claude import invoke_claude_agent
from beckett.loop.deps import RoleDeps
from beckett.loop.gws_util import gws_env
from beckett.loop.phase_state import (
    elapsed_minutes,
    save_phase_state,
    touch_observation,
)
from beckett.loop.preflight import CalendarClient
from beckett.loop.spec import GuardOutcome

log = logging.getLogger(__name__)

_JSON_OBJ = re.compile(r"\{[^{}]*\}")


class PostMeetingResult(BaseModel):
    meetings_processed: int = 0
    tasks_created: int = 0


def _event_id(ev: dict) -> str:
    return str(ev.get("id") or "")


def _needs_post(ev: dict, deps: RoleDeps) -> bool:
    eid = _event_id(ev)
    if not eid:
        return False
    key = f"{eid}:post_meeting"
    return key not in deps.phase_state.observation_written


def _ended_targets(deps: RoleDeps) -> list[dict]:
    cal = CalendarClient(gws_env(deps))
    return [e for e in cal.recently_ended_meetings(minutes_ago=90) if _needs_post(e, deps)]


async def orient_post_meeting_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_orient_post_meeting) < 30:
        return GuardOutcome(triggered=False, detail="post-meeting interval <30m")
    targets = _ended_targets(deps)
    if not targets:
        return GuardOutcome(triggered=False, detail="no recently ended meetings to process")
    return GuardOutcome(
        triggered=True,
        detail=f"{len(targets)} recently ended meeting(s) pending follow-up",
    )


def _parse_post(raw: str) -> tuple[int, int]:
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            return (
                int(d.get("meetings_processed") or d.get("processed") or 0),
                int(d.get("tasks_created") or d.get("tasks") or 0),
            )
    except json.JSONDecodeError:
        pass
    for m in _JSON_OBJ.finditer(raw or ""):
        try:
            d = json.loads(m.group())
            if isinstance(d, dict):
                return (
                    int(d.get("meetings_processed") or d.get("processed") or 0),
                    int(d.get("tasks_created") or d.get("tasks") or 0),
                )
        except json.JSONDecodeError:
            continue
    return 0, 0


async def orient_post_meeting_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    targets = _ended_targets(deps)
    titles = "; ".join(
        str(ev.get("summary") or _event_id(ev)) for ev in targets[:25]
    ) or "(meetings)"

    ids_line = ",".join(_event_id(ev) for ev in targets if _event_id(ev))
    prompt = (
        f"Role: {deps.role}\n"
        f"Recently ended calendar events ({len(targets)}): {titles}\n"
        f"event_ids: {ids_line}\n"
        "Follow up transcripts, summaries, and Todoist actions. Persist to Memory/. "
        '{"meetings_processed": N, "tasks_created": N} JSON only.'
    )
    raw = invoke_claude_agent("beckett-orient-post-meeting", prompt, deps)
    mp, tc = _parse_post(raw)
    for ev in targets:
        eid = _event_id(ev)
        if eid:
            touch_observation(eid, "post_meeting", deps.phase_state)
    deps.phase_state.last_orient_post_meeting = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return PostMeetingResult(
        meetings_processed=mp or len(targets),
        tasks_created=tc,
    ).model_dump(mode="json")
