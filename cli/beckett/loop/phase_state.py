"""Persistent per-role phase timings and observation dedupe keys."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class PhaseState(BaseModel):
    """Last-run timestamps and observation dedupe map (UTC)."""

    last_observe_rss: Optional[datetime] = None
    last_observe_context_refresh: Optional[datetime] = None
    last_orient_decisions: Optional[datetime] = None
    last_orient_email: Optional[datetime] = None
    last_orient_hygiene: Optional[datetime] = None
    last_orient_reply_drafter: Optional[datetime] = None
    last_orient_todo_forwarder: Optional[datetime] = None
    last_orient_meeting_prep: Optional[datetime] = None
    last_orient_post_meeting: Optional[datetime] = None
    last_act: Optional[datetime] = None
    last_scheduled_staff_update: Optional[datetime] = None
    last_scheduled_efficiency_log: Optional[datetime] = None
    last_scheduled_efficiency_email: Optional[datetime] = None
    last_scheduled_desktop_archive: Optional[datetime] = None
    observation_written: dict[str, datetime] = Field(default_factory=dict)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_phase_state(role_dir: Path) -> PhaseState:
    path = role_dir / ".beckett-state" / "phase-state.json"
    if not path.is_file():
        return PhaseState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return PhaseState.model_validate(raw)
    except Exception as exc:
        log.warning("load_phase_state %s: %s — using defaults", path, exc)
        return PhaseState()


def save_phase_state(role_dir: Path, state: PhaseState) -> None:
    d = role_dir / ".beckett-state"
    d.mkdir(parents=True, exist_ok=True)
    target = d / "phase-state.json"
    payload = json.dumps(state.model_dump(mode="json"), indent=2)

    fd, tmppath = tempfile.mkstemp(dir=str(d), prefix=".phase-state-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmppath, target)
    except Exception:
        try:
            Path(tmppath).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def elapsed_minutes(ts: Optional[datetime]) -> float:
    if ts is None:
        return float("inf")
    now = _utc_now()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 60.0)


def should_write_observation(
    entity_id: str, signal_type: str, state: PhaseState, ttl_minutes: float = 60.0
) -> bool:
    key = f"{entity_id}:{signal_type}"
    last = state.observation_written.get(key)
    return elapsed_minutes(last) >= ttl_minutes


def touch_observation(entity_id: str, signal_type: str, state: PhaseState) -> None:
    key = f"{entity_id}:{signal_type}"
    state.observation_written[key] = _utc_now()
