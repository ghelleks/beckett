"""Email triage per account — beckett-orient-email."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from beckett.loop.claude import invoke_claude_agent
from beckett.loop.deps import RoleDeps
from beckett.loop.gws_util import gws_env
from beckett.loop.phase_state import elapsed_minutes, save_phase_state
from beckett.loop.preflight import inbox_guard
from beckett.loop.spec import GuardOutcome

log = logging.getLogger(__name__)

_JSON_OBJ = re.compile(r"\{[^{}]*\}")


class EmailOrientResult(BaseModel):
    accounts_processed: int = 0
    classified: int = 0


def _beckett_gmail_accounts(deps: RoleDeps) -> list[str]:
    raw = deps.env.get("BECKETT_GMAIL_ACCOUNTS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    prof = deps.env.get("GWS_PROFILE", "").strip()
    return [deps.role if not prof else prof]


def _parse_classified(raw: str) -> int:
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            return int(d.get("classified") or d.get("classified_count") or 0)
        if isinstance(d, list):
            return len(d)
    except json.JSONDecodeError:
        pass
    for m in _JSON_OBJ.finditer(raw):
        try:
            d = json.loads(m.group())
            if isinstance(d, dict):
                return int(d.get("classified") or 0)
        except json.JSONDecodeError:
            continue
    nums = [int(x) for x in re.findall(r'"classified"\s*:\s*(\d+)', raw)]
    return max(nums) if nums else 0


async def orient_email_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_orient_email) < 15:
        return GuardOutcome(triggered=False, detail="orient-email interval <15m")
    env = gws_env(deps)
    cfg = env.get("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", "").strip()
    chk = inbox_guard(cfg or None)
    if not chk.get("eligible"):
        return GuardOutcome(triggered=False, detail="inbox_guard: empty or unavailable")
    return GuardOutcome(triggered=True, detail=f'inbox_guard eligible ({chk.get("unread_count", 0)} unread)')


async def orient_email_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    classified_total = 0
    profiles = _beckett_gmail_accounts(deps)

    def _one(profile: str) -> tuple[str, int]:
        merged = dict(gws_env(deps))
        merged_base = deps.env.get("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", "").strip()
        if profile != deps.role:
            cand = Path(f"~/.config/gws-{profile}").expanduser()
            if cand.is_dir():
                merged["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = str(cand)
            elif "/" in profile or profile.startswith("~"):
                merged["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = str(Path(profile).expanduser())
            elif not merged_base:
                merged.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", "")
        acc = deps.model_copy(update={"env": {**deps.env, **merged}})
        prompt = (
            f"Role: {deps.role}\nGmail profile/config: {profile}\n"
            "Run email triage via /beckett-email-classifier. "
            "Return JSON {{\"classified\": <int>}} only."
        )
        raw_out = invoke_claude_agent(
            "beckett-orient-email-account",
            prompt,
            acc,
        )
        return profile, _parse_classified(raw_out)

    with ThreadPoolExecutor(max_workers=min(3, max(1, len(profiles)))) as ex:
        futures = [ex.submit(_one, profile) for profile in profiles]
        for fut in as_completed(futures):
            try:
                _prof, cnt = fut.result()
                classified_total += cnt
            except Exception as exc:
                log.warning("orient_email_worker failed role=%s: %s", deps.role, exc)

    deps.phase_state.last_orient_email = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return EmailOrientResult(
        accounts_processed=len(profiles),
        classified=classified_total,
    ).model_dump(mode="json")
