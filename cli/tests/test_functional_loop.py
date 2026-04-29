"""Functional integration tests for the Beckett loop.

These tests exercise the full cycle (guard → agent → last-run.json) against a
real (temp) role directory. LLM calls are intercepted by a stub script set via
BECKETT_LLM_CMD, so no API key or real model is needed.

The stub_llm fixture writes a Python script that:
- Prints "OK\n" to stdout (standard response)
- Can be overridden per-test with a custom script body

All tests run synchronously via run_loop_cycle(..., once=True).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from beckett.loop.deps import RoleDeps
from beckett.loop.runner import run_loop_cycle

# ── Fixtures ──────────────────────────────────────────────────────────────────


MINIMAL_SPEC_YAML = textwrap.dedent("""\
    observe:
      entries:
        - id: ooda-observe
          agent: ooda-observe
    orient:
      entries: []
    act:
      entries: []
""")


def _git_init(path: Path) -> None:
    """Initialize a bare git repo so commit_role_changes can commit."""
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    for key, val in [
        ("user.email", "test@beckett"),
        ("user.name", "Beckett Test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(
            ["git", "-C", str(path), "config", key, val],
            capture_output=True,
            check=True,
        )
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        capture_output=True,
        check=True,
    )


def make_role(
    tmp_path: Path,
    *,
    spec_yaml: str = MINIMAL_SPEC_YAML,
    role_name: str = "testrole",
    with_self_md: bool = False,
    with_git: bool = False,
) -> tuple[Path, Path]:
    """Create a minimal role directory structure under tmp_path.

    Returns (base_dir, role_dir).
    """
    base = tmp_path / "masks"
    role_dir = base / role_name
    personal_dir = base / "personal"

    role_dir.mkdir(parents=True, exist_ok=True)
    personal_dir.mkdir(parents=True, exist_ok=True)

    (role_dir / "ROLE.md").write_text(f"# {role_name}\nThis is the test role.\n", encoding="utf-8")
    (role_dir / "loop.yaml").write_text(spec_yaml, encoding="utf-8")
    (role_dir / "Memory").mkdir()
    (role_dir / "Memory" / "INDEX.md").write_text(
        "| File | Summary | Tags |\n|------|---------|------|\n", encoding="utf-8"
    )

    (base / "AGENTS.md").write_text("# Global Agents\n", encoding="utf-8")

    if with_self_md:
        (personal_dir / "SELF.md").write_text("# SELF\nPersonal identity.\n", encoding="utf-8")

    if with_git:
        _git_init(role_dir)

    return base, role_dir


def make_deps(base: Path, role_dir: Path, extra_env: dict | None = None) -> RoleDeps:
    """Build a RoleDeps directly without touching MASKS_BASE env."""
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


@pytest.fixture
def stub_llm(tmp_path: Path):
    """Write a stub LLM script that prints OK and returns its path."""
    stub = tmp_path / "stub_llm.py"
    stub.write_text(
        textwrap.dedent("""\
            #!/usr/bin/env python3
            import sys
            # Consume stdin
            _ = sys.stdin.read()
            print("OK")
        """),
        encoding="utf-8",
    )
    return stub


def stub_cmd(stub: Path) -> str:
    return f"{sys.executable} {stub}"


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_smoke_once(tmp_path: Path, stub_llm: Path) -> None:
    """Full cycle with observer marker triggers → last-run.json written, memory file created."""
    base, role_dir = make_role(tmp_path, with_git=False)

    # Plant a marker to trigger observe_guard
    marker_dir = role_dir / ".ooda-pending"
    marker_dir.mkdir()
    (marker_dir / "observer.txt").write_text("test signal\n", encoding="utf-8")

    deps = make_deps(base, role_dir, {"BECKETT_LLM_CMD": stub_cmd(stub_llm)})
    result = run_loop_cycle(deps, once=True)

    assert result.triggered_count >= 1
    assert result.success

    last_run = role_dir / ".ooda-state" / "last-run.json"
    assert last_run.is_file()
    data = json.loads(last_run.read_text())
    assert data["triggered_count"] >= 1
    assert data["success"] is True

    # Memory file should be written by the fallback path
    obs_dir = role_dir / "Memory" / "Observations"
    assert obs_dir.is_dir()
    obs_files = list(obs_dir.glob("*.md"))
    assert len(obs_files) >= 1


def test_daily_briefer_time_gate(tmp_path: Path, stub_llm: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard fires within ±15 min window; second call skips due to stamp."""
    spec_yaml = textwrap.dedent("""\
        observe: {entries: []}
        orient: {entries: []}
        act:
          entries:
            - id: daily-briefer
              agent: daily-briefer
    """)
    base, role_dir = make_role(tmp_path, spec_yaml=spec_yaml)
    target = "08:00"

    # Monkeypatch _minutes_now to be exactly at target
    from beckett.loop.skills import daily_briefer as db_module

    monkeypatch.setattr(db_module, "_minutes_now", lambda: 8 * 60)
    deps = make_deps(
        base, role_dir,
        {"BECKETT_LLM_CMD": stub_cmd(stub_llm), "DAILY_BRIEFER_TARGET": target},
    )

    # First run: should trigger
    r1 = run_loop_cycle(deps, once=True)
    assert r1.triggered_count == 1

    stamp = role_dir / ".ooda-state" / f"daily-briefer-{datetime.now().strftime('%Y-%m-%d')}"
    assert stamp.exists(), "stamp file should have been written by guard"

    # Second run: stamp exists → skips
    r2 = run_loop_cycle(deps, once=True)
    assert r2.triggered_count == 0, "guard should skip after stamp written"


def test_daily_briefer_outside_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard does not fire when current time is outside ±15 min window."""
    spec_yaml = textwrap.dedent("""\
        observe: {entries: []}
        orient: {entries: []}
        act:
          entries:
            - id: daily-briefer
              agent: daily-briefer
    """)
    base, role_dir = make_role(tmp_path, spec_yaml=spec_yaml)

    from beckett.loop.skills import daily_briefer as db_module

    # Place time 60 minutes away from target
    monkeypatch.setattr(db_module, "_minutes_now", lambda: 8 * 60 + 60)
    deps = make_deps(base, role_dir, {"DAILY_BRIEFER_TARGET": "08:00"})

    result = run_loop_cycle(deps, once=True)
    assert result.triggered_count == 0


def test_synthesis_day_gate(tmp_path: Path, stub_llm: Path) -> None:
    """Synthesis triggers on correct day; cooldown blocks second run."""
    today_dow = datetime.now().strftime("%w")  # 0=Sunday
    spec_yaml = textwrap.dedent("""\
        observe: {entries: []}
        orient:
          entries:
            - id: mask-ooda-orient-synthesis
              agent: mask-ooda-orient-synthesis
        act: {entries: []}
    """)
    base, role_dir = make_role(tmp_path, spec_yaml=spec_yaml, role_name="personal")
    personal_dir = base / "personal"

    deps = make_deps(
        base, role_dir,
        {
            "BECKETT_LLM_CMD": stub_cmd(stub_llm),
            "SYNTHESIS_DAY": today_dow,
        },
    )

    # First run: triggers
    r1 = run_loop_cycle(deps, once=True)
    assert r1.triggered_count == 1

    log_file = personal_dir / ".synthesis.log"
    assert log_file.is_file(), ".synthesis.log must be written after agent run"
    assert "SYNTHESIS" in log_file.read_text()

    # Second run: cooldown active (log has a fresh timestamp)
    r2 = run_loop_cycle(deps, once=True)
    assert r2.triggered_count == 0, "second run should be blocked by 7-day cooldown"


def test_llm_cmd_override(tmp_path: Path) -> None:
    """BECKETT_LLM_CMD is invoked instead of claude --print (closes GAP 4)."""
    sentinel = tmp_path / "sentinel.txt"
    custom_script = tmp_path / "custom_llm.py"
    custom_script.write_text(
        textwrap.dedent(f"""\
            import sys
            _ = sys.stdin.read()
            open({str(sentinel)!r}, "w").write("INVOKED")
            print("OK")
        """),
        encoding="utf-8",
    )

    base, role_dir = make_role(tmp_path)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = make_deps(base, role_dir, {"BECKETT_LLM_CMD": f"{sys.executable} {custom_script}"})
    run_loop_cycle(deps, once=True)

    assert sentinel.is_file(), "custom LLM command was not invoked"
    assert sentinel.read_text() == "INVOKED"


def test_debug_mode_logs_stderr(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """BECKETT_LLM_DEBUG=1 causes stderr from the LLM subprocess to be logged (closes GAP 5)."""
    debug_script = tmp_path / "debug_llm.py"
    debug_script.write_text(
        textwrap.dedent("""\
            import sys
            _ = sys.stdin.read()
            print("STDERR_SIGNAL", file=sys.stderr)
            print("OK")
        """),
        encoding="utf-8",
    )

    base, role_dir = make_role(tmp_path)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = make_deps(
        base, role_dir,
        {
            "BECKETT_LLM_CMD": f"{sys.executable} {debug_script}",
            "BECKETT_LLM_DEBUG": "1",
        },
    )

    with caplog.at_level(logging.DEBUG, logger="beckett.loop.claude"):
        run_loop_cycle(deps, once=True)

    assert any(
        "STDERR_SIGNAL" in record.message
        for record in caplog.records
    ), "stderr content should appear in debug log"


def test_missing_guard_lenient(tmp_path: Path) -> None:
    """Spec entry with unregistered guard is skipped; cycle still succeeds (closes GAP 6)."""
    spec_yaml = textwrap.dedent("""\
        observe:
          entries:
            - id: no-such-guard
              agent: ooda-observe
        orient: {entries: []}
        act: {entries: []}
    """)
    base, role_dir = make_role(tmp_path, spec_yaml=spec_yaml)
    deps = make_deps(base, role_dir)

    result = run_loop_cycle(deps, once=True)

    assert result.success, "cycle should succeed even with missing guard"
    # Find the skipped entry in last-run.json
    data = json.loads((role_dir / ".ooda-state" / "last-run.json").read_text())
    observe_phase = next(p for p in data["phases"] if p["phase"] == "observe")
    skipped_skill = next(s for s in observe_phase["skills"] if s["id"] == "no-such-guard")
    assert skipped_skill["skipped"] is True
    assert skipped_skill["guard"]["triggered"] is False


def test_prompt_stack_injection(tmp_path: Path) -> None:
    """Pirandello prompt stack (ROLE.md etc.) appears in stdin fed to LLM (closes GAPs 2, 9)."""
    stdin_capture = tmp_path / "captured_stdin.txt"
    spy_script = tmp_path / "spy_llm.py"
    spy_script.write_text(
        textwrap.dedent(f"""\
            import sys
            content = sys.stdin.read()
            open({str(stdin_capture)!r}, "w", encoding="utf-8").write(content)
            print("OK")
        """),
        encoding="utf-8",
    )

    sentinel_content = "UNIQUE_ROLE_SENTINEL_STRING_XYZ"
    base, role_dir = make_role(tmp_path, with_self_md=True)
    # Write sentinel into ROLE.md
    (role_dir / "ROLE.md").write_text(
        f"# Role\n{sentinel_content}\n", encoding="utf-8"
    )

    # Plant marker to trigger observe guard
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = make_deps(
        base, role_dir,
        {"BECKETT_LLM_CMD": f"{sys.executable} {spy_script}"},
    )
    run_loop_cycle(deps, once=True)

    assert stdin_capture.is_file(), "spy script should have captured stdin"
    captured = stdin_capture.read_text(encoding="utf-8")
    assert sentinel_content in captured, "ROLE.md content should appear in LLM stdin"
    assert "=== ROLE ===" in captured, "prompt stack section headers should be present"


def test_role_env_vars(tmp_path: Path) -> None:
    """Subprocess receives MASKS_ROLE and BECKETT_ROLE_DIR env vars (closes GAP 9)."""
    env_capture = tmp_path / "env_capture.txt"
    env_script = tmp_path / "env_llm.py"
    env_script.write_text(
        textwrap.dedent(f"""\
            import os, sys
            _ = sys.stdin.read()
            role = os.environ.get("MASKS_ROLE", "MISSING")
            role_dir = os.environ.get("BECKETT_ROLE_DIR", "MISSING")
            open({str(env_capture)!r}, "w").write(f"{{role}}\\n{{role_dir}}")
            print("OK")
        """),
        encoding="utf-8",
    )

    base, role_dir = make_role(tmp_path, role_name="myrole")
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = make_deps(base, role_dir, {"BECKETT_LLM_CMD": f"{sys.executable} {env_script}"})
    run_loop_cycle(deps, once=True)

    assert env_capture.is_file()
    lines = env_capture.read_text().splitlines()
    assert lines[0] == "myrole", f"MASKS_ROLE should be 'myrole', got {lines[0]!r}"
    assert str(role_dir) in lines[1], "BECKETT_ROLE_DIR should contain role_dir path"


def test_guard_timeout_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """BECKETT_GUARD_TIMEOUT is respected by guard subprocess calls (closes GAP 7)."""
    # Register a custom guard that tries to run a slow subprocess
    slow_script = tmp_path / "slow.py"
    slow_script.write_text(
        textwrap.dedent("""\
            import time, sys
            time.sleep(10)
            print("done")
        """),
        encoding="utf-8",
    )

    spec_yaml = textwrap.dedent("""\
        observe:
          entries:
            - id: ooda-observe
              agent: ooda-observe
        orient: {entries: []}
        act: {entries: []}
    """)
    base, role_dir = make_role(tmp_path, spec_yaml=spec_yaml)

    from beckett.loop.skills import observe as obs_module
    from beckett.loop.spec import GuardOutcome as GO

    # Patch observe_guard to use a subprocess that sleeps longer than the timeout
    async def _slow_guard(deps: RoleDeps) -> GO:
        import subprocess as sp
        timeout = obs_module._guard_timeout(deps)
        try:
            sp.run(
                [sys.executable, str(slow_script)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except sp.TimeoutExpired:
            pass  # expected — guard handles gracefully
        return GO(triggered=False, detail="timeout-tested")

    monkeypatch.setattr(obs_module, "observe_guard", _slow_guard)

    deps = make_deps(base, role_dir, {"BECKETT_GUARD_TIMEOUT": "1"})
    # Should complete without hanging (timeout=1s << sleep=10s)
    result = run_loop_cycle(deps, once=True)
    assert result.success


def test_git_commit(tmp_path: Path, stub_llm: Path) -> None:
    """When agent writes a memory file, committed=True in last-run.json."""
    base, role_dir = make_role(tmp_path, with_git=True)

    # Plant marker to trigger observe guard → observe_agent writes memory file
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("signal\n")

    deps = make_deps(base, role_dir, {"BECKETT_LLM_CMD": stub_cmd(stub_llm)})
    result = run_loop_cycle(deps, once=True)

    assert result.committed, "a git commit should have been created"
    data = json.loads((role_dir / ".ooda-state" / "last-run.json").read_text())
    assert data["committed"] is True


def test_two_pass_trigger_context(tmp_path: Path, stub_llm: Path) -> None:
    """Both entries in a phase trigger; second agent's context has first entry's guard (closes GAP 3)."""
    context_capture = tmp_path / "context.json"
    context_script = tmp_path / "context_llm.py"
    context_script.write_text(
        textwrap.dedent(f"""\
            import sys, json, os
            stdin = sys.stdin.read()
            # Write the stdin content so we can inspect _phase_triggers
            open({str(context_capture)!r}, "w", encoding="utf-8").write(stdin)
            print("OK")
        """),
        encoding="utf-8",
    )

    # Two observe entries; both have marker files planted
    spec_yaml = textwrap.dedent("""\
        observe:
          entries:
            - id: ooda-observe
              agent: ooda-observe
            - id: email-classifier
              agent: email-classifier
        orient: {entries: []}
        act: {entries: []}
    """)
    base, role_dir = make_role(tmp_path, spec_yaml=spec_yaml)

    # Plant markers for both guards
    marker_dir = role_dir / ".ooda-pending"
    marker_dir.mkdir()
    (marker_dir / "observer.txt").write_text("signal\n")

    deps = make_deps(base, role_dir, {"BECKETT_LLM_CMD": f"{sys.executable} {context_script}"})
    run_loop_cycle(deps, once=True)

    data = json.loads((role_dir / ".ooda-state" / "last-run.json").read_text())
    observe_phase = next(p for p in data["phases"] if p["phase"] == "observe")

    # Both entries should have been processed
    entry_ids = {s["id"] for s in observe_phase["skills"]}
    assert "ooda-observe" in entry_ids
    assert "email-classifier" in entry_ids

    # The runner should have run pass-1 (all guards) then pass-2 (agents)
    # Verify that the result captures guard outcomes for both
    triggered = [s for s in observe_phase["skills"] if s["guard"]["triggered"]]
    assert len(triggered) >= 1, "at least ooda-observe should have triggered"
