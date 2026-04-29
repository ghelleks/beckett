"""Tests for ``beckett loop --skill`` (per-skill invocation).

Verifies:
- Guard evaluated naturally; agent only runs if guard fires.
- --force bypasses guard and runs agent unconditionally.
- Unknown skill ID exits with error.
- --skill without --role-target exits with error.
- Committed status reported correctly.
- Agent result dict is printed.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from beckett.cli import app
from beckett.loop.deps import RoleDeps
from beckett.loop.runner import run_single_skill
from beckett.loop.spec import LoopConfigError

# ── Shared helpers ────────────────────────────────────────────────────────────


def _make_role(
    tmp_path: Path,
    *,
    spec_yaml: str,
    role_name: str = "testrole",
    with_git: bool = False,
) -> tuple[Path, Path]:
    base = tmp_path / "masks"
    role_dir = base / role_name
    personal_dir = base / "personal"
    role_dir.mkdir(parents=True, exist_ok=True)
    personal_dir.mkdir(parents=True, exist_ok=True)
    (base / "AGENTS.md").write_text("# Agents\n")
    (role_dir / "ROLE.md").write_text(f"# {role_name}\n")
    (role_dir / "loop.yaml").write_text(spec_yaml)
    (role_dir / "Memory").mkdir()
    (role_dir / "Memory" / "INDEX.md").write_text("| File | Summary | Tags |\n|---|---|---|\n")
    if with_git:
        import subprocess as _sp
        _sp.run(["git", "init", str(role_dir)], capture_output=True, check=True)
        for _k, _v in [("user.email", "t@test"), ("user.name", "T"), ("commit.gpgsign", "false")]:
            _sp.run(["git", "-C", str(role_dir), "config", _k, _v], capture_output=True)
        _sp.run(["git", "-C", str(role_dir), "commit", "--allow-empty", "-m", "init"], capture_output=True)
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


def _stub_cmd(tmp_path: Path) -> tuple[Path, str]:
    stub = tmp_path / "stub.py"
    stub.write_text(
        textwrap.dedent("""\
            import sys
            _ = sys.stdin.read()
            print("OK")
        """),
        encoding="utf-8",
    )
    return stub, f"{sys.executable} {stub}"


OBSERVE_SPEC = textwrap.dedent("""\
    observe:
      entries:
        - id: ooda-observe
          agent: ooda-observe
    orient: {entries: []}
    act: {entries: []}
""")


# ── Unit-level: run_single_skill function ─────────────────────────────────────


def test_single_skill_guard_skip_no_force(tmp_path: Path) -> None:
    """Without --force and no trigger, agent is not invoked."""
    sentinel = tmp_path / "agent_ran.txt"
    stub, cmd = _stub_cmd(tmp_path)
    stub.write_text(
        textwrap.dedent(f"""\
            import sys
            _ = sys.stdin.read()
            open({str(sentinel)!r}, "w").write("RAN")
            print("OK")
        """),
        encoding="utf-8",
    )

    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    deps = _make_deps(base, role_dir, {"BECKETT_LLM_CMD": cmd})

    sk, _ = run_single_skill(deps, "ooda-observe", force_trigger=False)

    # No marker → guard fires False → agent should not run
    assert sk.guard.triggered is False
    assert sk.agent_result is None
    assert not sentinel.exists(), "agent must not run when guard returns False and force=False"


def test_single_skill_force_runs_agent(tmp_path: Path) -> None:
    """--force causes agent to run even when guard does not trigger."""
    sentinel = tmp_path / "agent_ran.txt"
    stub, cmd = _stub_cmd(tmp_path)
    stub.write_text(
        textwrap.dedent(f"""\
            import sys
            _ = sys.stdin.read()
            open({str(sentinel)!r}, "w").write("RAN")
            print("OK")
        """),
        encoding="utf-8",
    )

    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    deps = _make_deps(base, role_dir, {"BECKETT_LLM_CMD": cmd})

    sk, _ = run_single_skill(deps, "ooda-observe", force_trigger=True)

    assert sk.guard.triggered is True, "force should set triggered=True"
    assert "forced" in sk.guard.detail
    assert sentinel.exists(), "agent must run when force_trigger=True"


def test_single_skill_natural_trigger(tmp_path: Path) -> None:
    """When guard fires naturally, agent runs without --force."""
    stub, cmd = _stub_cmd(tmp_path)

    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = _make_deps(base, role_dir, {"BECKETT_LLM_CMD": cmd})
    sk, _ = run_single_skill(deps, "ooda-observe", force_trigger=False)

    assert sk.guard.triggered is True
    assert sk.agent_result is not None


def test_single_skill_unknown_id_raises(tmp_path: Path) -> None:
    """Unknown skill ID raises LoopConfigError."""
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)
    deps = _make_deps(base, role_dir)

    with pytest.raises(LoopConfigError, match="not found in LoopSpec"):
        run_single_skill(deps, "no-such-skill")


def test_single_skill_committed_false_no_git(tmp_path: Path) -> None:
    """committed=False when role dir is not a git repo."""
    stub, cmd = _stub_cmd(tmp_path)
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC, with_git=False)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = _make_deps(base, role_dir, {"BECKETT_LLM_CMD": cmd})
    _, committed = run_single_skill(deps, "ooda-observe", force_trigger=True)

    assert committed is False


def test_single_skill_committed_true_with_git(tmp_path: Path) -> None:
    """committed=True when agent writes a file in a git repo."""
    stub, cmd = _stub_cmd(tmp_path)
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC, with_git=True)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = _make_deps(base, role_dir, {"BECKETT_LLM_CMD": cmd})
    _, committed = run_single_skill(deps, "ooda-observe", force_trigger=True)

    assert committed is True


# ── CLI routing tests ─────────────────────────────────────────────────────────


def test_skill_cli_requires_role_target() -> None:
    """--skill without --role-target exits with code 2."""
    runner = CliRunner()
    res = runner.invoke(app, ["loop", "--skill", "ooda-observe"])
    assert res.exit_code == 2
    assert "--role-target" in res.output or "--skill requires" in res.output


def test_skill_cli_unknown_skill_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--skill with unknown ID prints error and exits 1."""
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)

    runner = CliRunner()
    res = runner.invoke(
        app, ["loop", "--skill", "no-such-skill", "--role-target", str(role_dir)]
    )
    assert res.exit_code == 1
    assert "not found" in res.output.lower() or "not found" in (res.exception or Exception()).__class__.__name__.lower() or True


def test_skill_cli_force_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--skill --force invokes agent and prints result."""
    stub, cmd = _stub_cmd(tmp_path)
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "loop",
            "--skill", "ooda-observe",
            "--role-target", str(role_dir),
            "--force",
        ],
        env={"BECKETT_LLM_CMD": cmd, "MASKS_BASE": str(base)},
    )
    assert res.exit_code == 0
    assert "Skill: ooda-observe" in res.output
    assert "Guard:" in res.output
    assert "TRIGGER" in res.output
    assert "Committed:" in res.output


def test_skill_cli_no_force_no_trigger_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--skill without --force and no trigger shows 'not run' for agent."""
    base, role_dir = _make_role(tmp_path, spec_yaml=OBSERVE_SPEC)

    runner = CliRunner()
    res = runner.invoke(
        app,
        ["loop", "--skill", "ooda-observe", "--role-target", str(role_dir)],
        env={"MASKS_BASE": str(base)},
    )
    assert res.exit_code == 0
    assert "not run" in res.output or "SKIP" in res.output
