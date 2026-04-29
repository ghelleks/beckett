"""Tests for ``beckett status --verbose``.

Verifies that verbose status output shows full per-phase, per-skill detail
from last-run.json, including guard outcomes, agent result fields, and errors.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from beckett.cli import app
from beckett.status_cmd import status_cmd

# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_last_run(role_dir: Path, data: dict) -> None:
    state = role_dir / ".ooda-state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "last-run.json").write_text(json.dumps(data), encoding="utf-8")


def _minimal_run(
    *,
    role: str = "testrole",
    triggered: int = 1,
    total: int = 2,
    success: bool = True,
    committed: bool = False,
    phases: list | None = None,
) -> dict:
    return {
        "role": role,
        "started_at": "2026-04-29T10:00:00+00:00",
        "finished_at": "2026-04-29T10:01:00+00:00",
        "triggered_count": triggered,
        "total_entries": total,
        "success": success,
        "fatal": False,
        "committed": committed,
        "phases": phases or [],
    }


def _make_role(tmp_path: Path, name: str = "testrole") -> Path:
    role = tmp_path / name
    role.mkdir(parents=True, exist_ok=True)
    (role / "ROLE.md").write_text(f"# {name}\n")
    return role


# ── status_cmd verbose=True ───────────────────────────────────────────────────


def test_verbose_no_run_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Roles with no last-run.json show '(no run data)' in verbose mode."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    _make_role(tmp_path, "work")

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    assert "no run data" in buf.getvalue()


def test_verbose_shows_role_and_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verbose output contains role name, triggered count, and success/committed."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(role_dir, _minimal_run(triggered=2, total=3, committed=True))

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    out = buf.getvalue()
    assert "ROLE: work" in out
    assert "2/3" in out
    assert "Committed: yes" in out


def test_verbose_phase_headers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Phase names appear in verbose output."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(
        role_dir,
        _minimal_run(phases=[
            {"phase": "observe", "skills": []},
            {"phase": "orient", "skills": []},
            {"phase": "act", "skills": []},
        ]),
    )

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    out = buf.getvalue()
    assert "Phase: observe" in out
    assert "Phase: orient" in out
    assert "Phase: act" in out


def test_verbose_triggered_skill_shows_arrow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Triggered skill shows ▶ icon and TRIGGER label."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(
        role_dir,
        _minimal_run(phases=[{
            "phase": "observe",
            "skills": [{
                "id": "ooda-observe",
                "guard": {"triggered": True, "detail": "3 unread"},
                "skipped": False,
                "agent_result": {"signals_found": 3, "files_written": 1, "sources": ["email"]},
                "error": None,
            }],
        }]),
    )

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    out = buf.getvalue()
    assert "▶" in out
    assert "TRIGGER" in out
    assert "3 unread" in out


def test_verbose_skipped_skill_shows_dot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-triggered skill shows · icon and SKIP label."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(
        role_dir,
        _minimal_run(phases=[{
            "phase": "act",
            "skills": [{
                "id": "ooda-act",
                "guard": {"triggered": False, "detail": "no actionable tasks"},
                "skipped": False,
                "agent_result": None,
                "error": None,
            }],
        }]),
    )

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    out = buf.getvalue()
    assert "·" in out
    assert "SKIP" in out
    assert "no actionable tasks" in out


def test_verbose_error_shown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Agent error string appears in verbose output."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(
        role_dir,
        _minimal_run(success=False, phases=[{
            "phase": "observe",
            "skills": [{
                "id": "ooda-observe",
                "guard": {"triggered": True, "detail": "2 unread"},
                "skipped": False,
                "agent_result": None,
                "error": "timeout after 1800s",
            }],
        }]),
    )

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    out = buf.getvalue()
    assert "ERROR" in out or "timeout" in out


def test_verbose_agent_result_fields_formatted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Agent result dict key=value pairs appear compactly formatted."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(
        role_dir,
        _minimal_run(phases=[{
            "phase": "orient",
            "skills": [{
                "id": "mask-ooda-orient-synthesis",
                "guard": {"triggered": True, "detail": "synthesis day"},
                "skipped": False,
                "agent_result": {"patterns_found": 4, "written": 2, "stale_updated": 1},
                "error": None,
            }],
        }]),
    )

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    out = buf.getvalue()
    assert "patterns_found=4" in out
    assert "written=2" in out


def test_verbose_skipped_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Entry skipped due to missing registry shows SKIP(X) marker."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(
        role_dir,
        _minimal_run(phases=[{
            "phase": "observe",
            "skills": [{
                "id": "no-such-guard",
                "guard": {"triggered": False, "detail": "skipped:missing-registry"},
                "skipped": True,
                "agent_result": None,
                "error": None,
            }],
        }]),
    )

    buf = StringIO()
    with patch("sys.stdout", buf):
        status_cmd((), verbose=True)

    assert "SKIP(X)" in buf.getvalue()


# ── CLI flag tests ────────────────────────────────────────────────────────────


def test_status_verbose_cli_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``beckett status --verbose`` routes to verbose=True."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(role_dir, _minimal_run())

    runner = CliRunner()
    res = runner.invoke(app, ["status", "--verbose"])

    assert res.exit_code == 0
    assert "ROLE: work" in res.output  # verbose-specific header


def test_status_verbose_short_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``beckett status -v`` is equivalent to --verbose."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(role_dir, _minimal_run())

    runner = CliRunner()
    res = runner.invoke(app, ["status", "-v"])

    assert res.exit_code == 0
    assert "ROLE: work" in res.output


def test_status_default_still_tabular(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without --verbose, output stays as the compact tabular format."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    role_dir = _make_role(tmp_path, "work")
    _write_last_run(role_dir, _minimal_run(triggered=1, total=2))

    runner = CliRunner()
    res = runner.invoke(app, ["status"])

    assert res.exit_code == 0
    assert "ROLE" in res.output  # column header
    assert "LAST_RUN" in res.output
    # Should NOT have verbose-specific header
    assert "ROLE: work" not in res.output
