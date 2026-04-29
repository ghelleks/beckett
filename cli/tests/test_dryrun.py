"""Tests for ``beckett loop --dry-run``.

Verifies that:
- All guards are evaluated and results collected.
- No agents are invoked (BECKETT_LLM_CMD stub is never called).
- Triggered / skipped entries are reflected in the LoopRunResult.
- The CLI command routes correctly and formats output.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from beckett.cli import app
from beckett.loop.deps import RoleDeps
from beckett.loop.runner import run_loop_dryrun

# ── Helpers (shared with test_functional_loop.py pattern) ────────────────────


def _make_role(
    tmp_path: Path,
    *,
    spec_yaml: str,
    role_name: str = "testrole",
) -> tuple[Path, Path]:
    base = tmp_path / "masks"
    role_dir = base / role_name
    personal_dir = base / "personal"
    role_dir.mkdir(parents=True, exist_ok=True)
    personal_dir.mkdir(parents=True, exist_ok=True)
    (base / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (role_dir / "ROLE.md").write_text(f"# {role_name}\n", encoding="utf-8")
    (role_dir / "loop.yaml").write_text(spec_yaml, encoding="utf-8")
    (role_dir / "Memory").mkdir()
    (role_dir / "Memory" / "INDEX.md").write_text("| File | Summary | Tags |\n|---|---|---|\n")
    return base, role_dir


def _make_deps(base: Path, role_dir: Path, extra_env: dict | None = None) -> RoleDeps:
    from beckett.loop.spec import load_loop_spec

    env: dict[str, str] = {"MASKS_BASE": str(base)}
    if extra_env:
        env.update(extra_env)
    spec = load_loop_spec(role_dir)
    return RoleDeps(
        role=role_dir.name,
        role_dir=role_dir,
        masks_base=base,
        personal_dir=base / "personal",
        env=env,
        loop_spec=spec,
    )


OBSERVE_SPEC = textwrap.dedent("""\
    observe:
      entries:
        - id: ooda-observe
          agent: ooda-observe
    orient: {entries: []}
    act: {entries: []}
""")

TWO_SKILL_SPEC = textwrap.dedent("""\
    observe:
      entries:
        - id: ooda-observe
          agent: ooda-observe
        - id: email-classifier
          agent: email-classifier
    orient: {entries: []}
    act: {entries: []}
""")


# ── Unit-level: run_loop_dryrun function ──────────────────────────────────────


def test_dryrun_no_triggers(tmp_path: Path) -> None:
    """When no guard conditions are met, triggered_count is 0."""
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    deps = _make_deps(base, role_dir)

    result = run_loop_dryrun(deps)

    assert result.triggered_count == 0
    assert result.total_entries == 1
    assert result.success is True
    assert len(result.phases) == 3  # observe, orient, act


def test_dryrun_trigger_on_marker(tmp_path: Path) -> None:
    """Observer marker causes ooda-observe to show as triggered."""
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = _make_deps(base, role_dir)
    result = run_loop_dryrun(deps)

    assert result.triggered_count == 1
    observe_phase = next(p for p in result.phases if p.phase == "observe")
    skill = observe_phase.skills[0]
    assert skill.id == "ooda-observe"
    assert skill.guard.triggered is True
    assert skill.agent_result is None, "dry-run must not invoke the agent"


def test_dryrun_does_not_invoke_llm(tmp_path: Path) -> None:
    """Even with triggers, BECKETT_LLM_CMD is never called during dry-run."""
    sentinel = tmp_path / "llm_called.txt"
    spy = tmp_path / "spy.py"
    spy.write_text(
        textwrap.dedent(f"""\
            import sys
            open({str(sentinel)!r}, "w").write("CALLED")
            print("OK")
        """),
        encoding="utf-8",
    )

    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = _make_deps(base, role_dir, {"BECKETT_LLM_CMD": f"{sys.executable} {spy}"})
    run_loop_dryrun(deps)

    assert not sentinel.exists(), "LLM subprocess must not be called during --dry-run"


def test_dryrun_missing_guard_skipped(tmp_path: Path) -> None:
    """Entry with unregistered guard shows as skipped in dry-run."""
    spec = textwrap.dedent("""\
        observe:
          entries:
            - id: no-such-guard
              agent: ooda-observe
        orient: {entries: []}
        act: {entries: []}
    """)
    base, role_dir = _make_role(tmp_path, spec_yaml=spec)
    deps = _make_deps(base, role_dir)

    result = run_loop_dryrun(deps)

    observe_phase = next(p for p in result.phases if p.phase == "observe")
    skill = observe_phase.skills[0]
    assert skill.skipped is True
    assert skill.guard.triggered is False


def test_dryrun_multiple_phases(tmp_path: Path) -> None:
    """Dry-run covers all three phases and returns results for each."""
    spec = textwrap.dedent("""\
        observe:
          entries:
            - id: ooda-observe
              agent: ooda-observe
        orient:
          entries:
            - id: mask-ooda-orient-synthesis
              agent: mask-ooda-orient-synthesis
        act:
          entries:
            - id: ooda-act
              agent: ooda-act
    """)
    base, role_dir = _make_role(tmp_path, spec_yaml=spec)
    deps = _make_deps(base, role_dir)

    result = run_loop_dryrun(deps)

    phase_names = [p.phase for p in result.phases]
    assert "observe" in phase_names
    assert "orient" in phase_names
    assert "act" in phase_names
    assert result.total_entries == 3


def test_dryrun_does_not_write_last_run(tmp_path: Path) -> None:
    """Dry-run does not write last-run.json (no side effects)."""
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    deps = _make_deps(base, role_dir)

    run_loop_dryrun(deps)

    assert not (role_dir / ".ooda-state" / "last-run.json").exists()


# ── CLI routing tests ─────────────────────────────────────────────────────────


def test_dryrun_cli_requires_role_target_or_masks_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--dry-run without --role-target scans MASKS_BASE (empty → no output)."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))  # empty → no roles
    runner = CliRunner()
    res = runner.invoke(app, ["loop", "--dry-run"])
    assert res.exit_code == 0  # empty base is fine, just no output


def test_dryrun_cli_output_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--dry-run output contains phase headers, trigger icons, and summary line."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path / "masks"))
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    runner = CliRunner()
    res = runner.invoke(app, ["loop", "--dry-run", "--role-target", str(role_dir)])

    assert res.exit_code == 0
    assert "DRY RUN" in res.output
    assert "Phase: observe" in res.output
    assert "▶" in res.output, "triggered entry should show ▶"
    assert "TRIGGER" in res.output
    assert "would trigger" in res.output


def test_dryrun_cli_skip_icon(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Skipped entries show · icon (no observer marker, no emails)."""
    monkeypatch.setenv("MASKS_BASE", str(tmp_path / "masks"))
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)

    runner = CliRunner()
    res = runner.invoke(app, ["loop", "--dry-run", "--role-target", str(role_dir)])

    assert res.exit_code == 0
    assert "·" in res.output
    assert "SKIP" in res.output
    assert "0 would trigger" in res.output
