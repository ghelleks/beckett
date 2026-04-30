"""Pre-flight helpers: inbox, Gmail, Calendar, Todoist via local CLIs (no MCP)."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _strip_gws_noise(stdout: str) -> str:
    return "\n".join(ln for ln in stdout.splitlines() if not ln.startswith("Using")).strip()


def _subprocess_json(argv: list[str], env: dict[str, str], timeout: float = 15.0) -> Any:
    import subprocess

    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            return None
        txt = _strip_gws_noise(proc.stdout)
        if not txt:
            return None
        return json.loads(txt)
    except Exception as exc:
        log.debug("preflight subprocess_json %s: %s", argv[:4], exc)
        return None


def inbox_guard(gws_config_dir: str | None = None) -> dict[str, Any]:
    """Return unread inbox eligibility using ``gws gmail +triage`` (Observe parity),
    falling back to the Gmail messages list API.
    """
    import subprocess

    env = dict(os.environ)
    if gws_config_dir:
        env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = str(Path(gws_config_dir).expanduser())

    unread_count = 0
    accounts: list[str] = []
    timeout = float(os.environ.get("BECKETT_GUARD_TIMEOUT") or os.environ.get("MASKS_GUARD_TIMEOUT") or "15")

    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode == 0:
            raw = _strip_gws_noise(proc.stdout)
            if raw:
                msgs = json.loads(raw)
                if isinstance(msgs, list):
                    unread_count = len(msgs)
    except Exception as exc:
        log.debug("inbox_guard triage fallback: %s", exc)

    if unread_count == 0:
        try:
            params = json.dumps(
                {"userId": "me", "labelIds": ["INBOX", "UNREAD"], "maxResults": 1}
            )
            data = _subprocess_json(
                ["gws", "gmail", "messages", "list", "--params", params],
                env=env,
                timeout=min(timeout or 15.0, 15.0),
            )
            if isinstance(data, dict):
                unread_count = max(
                    int(data.get("resultSizeEstimate") or 0),
                    len(data.get("messages") or []),
                )
        except Exception as exc:
            log.debug("inbox_guard messages.list fallback: %s", exc)

    acc = env.get("BECKETT_ACCOUNT_EMAIL", "").strip()
    if acc:
        accounts.append(acc)

    eligible = unread_count > 0
    return {"eligible": eligible, "unread_count": unread_count, "accounts": accounts}


class GmailClient:
    """Gmail pre-checks via gws CLI."""

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self.env = dict(env or os.environ)

    def _with_account(self, account: str | None) -> dict[str, str]:
        e = dict(self.env)
        if account:
            p = Path(account).expanduser()
            if p.is_dir():
                e["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = str(p)
            else:
                # treat as profile slug -> ~/.config/gws-<profile>
                e["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = str(
                    Path(f"~/.config/gws-{account}").expanduser()
                )
        return e

    def has_label(self, label: str, account: str | None = None) -> bool:
        """True if at least one inbox message matches Gmail query (label:&c)."""
        env = self._with_account(account)
        q = f"in:inbox label:{label}"
        params = json.dumps({"userId": "me", "q": q, "maxResults": 1})
        data = _subprocess_json(
            ["gws", "gmail", "messages", "list", "--params", params], env=env
        )
        if isinstance(data, dict):
            return bool(data.get("messages"))
        return False

    def unread_count(self, account: str | None = None) -> int:
        env = self._with_account(account)
        params = json.dumps(
            {"userId": "me", "labelIds": ["INBOX", "UNREAD"], "maxResults": 1}
        )
        data = _subprocess_json(
            ["gws", "gmail", "messages", "list", "--params", params], env=env
        )
        if isinstance(data, dict):
            return int(data.get("resultSizeEstimate") or len(data.get("messages") or []))
        return 0


class CalendarClient:
    """Calendar helpers via gws CLI."""

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self.env = dict(env or os.environ)

    def _list_events(self, time_min: datetime, time_max: datetime) -> list[dict[str, Any]]:
        params = json.dumps(
            {
                "calendarId": "primary",
                "timeMin": time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "timeMax": time_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 50,
            }
        )
        data = _subprocess_json(
            ["gws", "calendar", "events", "list", "--params", params],
            env=self.env,
            timeout=20.0,
        )
        if isinstance(data, dict):
            items = data.get("items") or []
            return [x for x in items if isinstance(x, dict)]
        return []

    def upcoming_meetings(self, hours_ahead: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        items = self._list_events(now, now + timedelta(hours=hours_ahead))
        return [
            e
            for e in items
            if "dateTime" in e.get("start", {})
            and e.get("status", "confirmed") != "cancelled"
        ]

    def recently_ended_meetings(self, minutes_ago: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        items = self._list_events(now - timedelta(minutes=minutes_ago), now)
        return [
            e
            for e in items
            if "dateTime" in e.get("end", {})
            and e.get("status", "confirmed") != "cancelled"
        ]


_JSON_BLOCK = re.compile(r"\[[\s\S]*\]|\{[\s\S]*\}")


def _parse_td_task_blocks(stdout: str) -> list[dict[str, Any]]:
    """Best-effort: extract task-like rows from td markdown/JSON-ish output."""
    out: list[dict[str, Any]] = []
    text = stdout.strip()
    if not text:
        return out
    # Try full JSON array
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    # Scan for embedded JSON array
    m = _JSON_BLOCK.search(text)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except json.JSONDecodeError:
            pass
    # Fallback: one task per non-empty line
    for ln in text.splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            out.append({"line": s})
    return out


class TodoistClient:
    """Todoist via ``td`` CLI."""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def _run_td(self, *args: str) -> str:
        import subprocess

        try:
            proc = subprocess.run(
                ["td", *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=os.environ,
            )
            return proc.stdout or ""
        except Exception as exc:
            log.debug("TodoistClient td %s: %s", args[:2], exc)
            return ""

    def overdue_tasks(self) -> list[dict[str, Any]]:
        out = self._run_td("find-tasks-by-date", "--start-date", "today")
        try:
            data = json.loads(out.strip())
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except json.JSONDecodeError:
            pass
        return _parse_td_task_blocks(out)

    def agent_tasks(self) -> list[dict[str, Any]]:
        return _parse_td_task_blocks(
            self._run_td("find-tasks", "--filter", "@agent")
        )

    def decision_tasks(self) -> list[dict[str, Any]]:
        return _parse_td_task_blocks(
            self._run_td("find-tasks", "--filter", "@decision")
        )
