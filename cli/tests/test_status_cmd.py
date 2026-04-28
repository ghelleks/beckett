from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from beckett.status_cmd import status_cmd


def _mk_role(base, name: str) -> None:
    role = base / name
    role.mkdir(parents=True, exist_ok=True)
    (role / "ROLE.md").write_text("# role\n", encoding="utf-8")


def test_status_reads_last_run_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    _mk_role(tmp_path, "work")
    state = tmp_path / "work" / ".ooda-state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "last-run.json").write_text(
        json.dumps({"finished_at": "2026-01-01T00:00:00+00:00", "triggered_count": 2, "total_entries": 5, "success": True}),
        encoding="utf-8",
    )
    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd(())
    out = buf.getvalue()
    assert "2/5" in out
    assert "yes" in out


def test_status_shows_never_when_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    _mk_role(tmp_path, "work")
    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd(())
    assert "never" in buf.getvalue()
