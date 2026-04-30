"""Todo forwarder — beckett-orient-todo-forwarder (no LLM)."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone

from pydantic import BaseModel

from beckett.loop.deps import RoleDeps
from beckett.loop.gws_util import guard_timeout, gws_env
from beckett.loop.phase_state import elapsed_minutes, save_phase_state
from beckett.loop.spec import GuardOutcome

log = logging.getLogger(__name__)


class TodoForwardResult(BaseModel):
    forwarded: int = 0
    failed: int = 0


def _todo_forward_candidates(env: dict[str, str], timeout: int) -> list[str]:
    params = json.dumps(
        {"userId": "me", "q": "in:inbox label:todo -label:todo-forwarded", "maxResults": 25}
    )
    try:
        proc = subprocess.run(
            ["gws", "gmail", "messages", "list", "--params", params],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            return []
        data = json.loads(proc.stdout or "{}")
        if not isinstance(data, dict):
            return []
        return [
            str(m["id"])
            for m in (data.get("messages") or [])
            if isinstance(m, dict) and m.get("id")
        ]
    except Exception as exc:
        log.debug("_todo_forward_candidates: %s", exc)
        return []


async def orient_todo_forwarder_guard(deps: RoleDeps) -> GuardOutcome:
    if elapsed_minutes(deps.phase_state.last_orient_todo_forwarder) < 15:
        return GuardOutcome(triggered=False, detail="todo-forwarder interval <15m")
    env = gws_env(deps)
    if not _todo_forward_candidates(env, guard_timeout(deps)):
        return GuardOutcome(triggered=False, detail="no unforwarded todo-labeled inbox mail")
    return GuardOutcome(triggered=True, detail="todo without todo-forwarded; interval elapsed")


def _modify_message(mid: str, env: dict[str, str], timeout: int, **kwargs: object) -> bool:
    body: dict[str, object] = {"id": mid}
    body.update(kwargs)
    params = json.dumps(body)
    proc = subprocess.run(
        ["gws", "gmail", "messages", "modify", "--params", params],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return proc.returncode == 0


async def orient_todo_forwarder_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    del guard, context
    dest = deps.env.get("TODOIST_EMAIL_INBOX", "").strip()
    if not dest:
        deps.phase_state.last_orient_todo_forwarder = datetime.now(timezone.utc)
        save_phase_state(deps.role_dir, deps.phase_state)
        return TodoForwardResult(
            forwarded=0, failed=0
        ).model_dump(mode="json")

    env = gws_env(deps)
    timeout = guard_timeout(deps)
    mids = _todo_forward_candidates(env, timeout)
    fwd, failed = 0, 0

    for mid in mids:
        fwd_proc = subprocess.run(
            ["gws", "gmail", "+forward", "--message-id", mid, "--to", dest],
            capture_output=True,
            text=True,
            timeout=max(timeout * 12, 60),
            env=env,
        )
        if fwd_proc.returncode != 0:
            log.warning(
                "gmail +forward failed id=%s: %s", mid, (fwd_proc.stderr or fwd_proc.stdout)[:400]
            )
            failed += 1
            continue

        if not _modify_message(
            mid,
            env,
            timeout,
            addLabelIds=["todo-forwarded"],
            removeLabelIds=["INBOX"],
        ):
            _modify_message(mid, env, timeout, addLabelIds=["todo-forwarded"])

        fwd += 1

    deps.phase_state.last_orient_todo_forwarder = datetime.now(timezone.utc)
    save_phase_state(deps.role_dir, deps.phase_state)
    return TodoForwardResult(forwarded=fwd, failed=failed).model_dump(mode="json")
