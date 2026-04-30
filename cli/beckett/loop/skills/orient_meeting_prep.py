"""Meeting prep — beckett-orient-meeting-prep."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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


class MeetingPrepResult(BaseModel):
    meetings_prepped: int = 0


def _event_id(ev: dict) -> str:
    return str(ev.get("id") or "")


def _needs_prep(ev: dict, deps: RoleDeps) -> bool:
    eid = _event_id(ev)
    if not eid:
        return False
    key = f"{eid}:meeting_prep"
    return key not in deps.phase_state.observation_written


def _meetings_to_prep(deps: RoleDeps) -> list[dict]:
    cal = CalendarClient(gws_env(deps))
    return [e for e in cal.upcoming_meetings(hours_ahead=24) if _needs_prep(e, deps)]


async def orient_meeting_prep_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_orient_meeting_prep) < 30:
        return GuardOutcome(triggered=False, detail="meeting-prep interval <30m")
    targets = _meetings_to_prep(deps)
    if not targets:
        return GuardOutcome(triggered=False, detail="no upcoming meetings needing prep")
    return GuardOutcome(
        triggered=True,
        detail=f"{len(targets)} meeting(s) need prep snapshot",
    )


def _prep_one(ev: dict, deps: RoleDeps) -> tuple[str | None, bool]:
    eid = _event_id(ev)
    if not eid:
        return None, False
    summary = ev.get("summary") or "(meeting)"
    start = ""
    try:
        st = ev.get("start") or {}
        start = str(st.get("dateTime") or st.get("date") or "")
    except Exception:
        pass
    prompt = (
        f"event_id: {eid}\n"
        f"title: {summary}\n"
        f"start: {start}\n"
        f"todoist_task_content: Prep notes for «{summary}»\n"
        f"todoist_task_due: {start}\n\n"
        "Prepare this single meeting via /beckett-meeting-prep-single. "
        "Return JSON {\"ok\":true} only when done."
    )
    raw = invoke_claude_agent("beckett-meeting-preparer", prompt, deps)
    ok = len((raw or "").strip()) > 20
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            ok = bool(d.get("ok", ok))
    except json.JSONDecodeError:
        pass
    for m in _JSON_OBJ.finditer(raw or ""):
        try:
            d = json.loads(m.group())
            if isinstance(d, dict) and "ok" in d:
                ok = bool(d.get("ok"))
        except json.JSONDecodeError:
            continue
    return eid if ok else None, ok


async def orient_meeting_prep_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    targets = _meetings_to_prep(deps)
    count = 0
    workers = max(1, min(4, len(targets)))

    def _runner(ev: dict) -> tuple[str | None, bool]:
        try:
            return _prep_one(ev, deps)
        except Exception as exc:
            log.warning("meeting prep failed role=%s: %s", deps.role, exc)
            return None, False

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_runner, ev) for ev in targets]
        for fut in as_completed(futures):
            eid, ok = fut.result()
            if ok and eid:
                touch_observation(eid, "meeting_prep", deps.phase_state)
                count += 1

    deps.phase_state.last_orient_meeting_prep = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return MeetingPrepResult(meetings_prepped=count).model_dump(mode="json")
