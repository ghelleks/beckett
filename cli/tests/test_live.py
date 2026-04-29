"""Live integration tests — require BECKETT_MODEL and real API credentials.

These tests are automatically skipped unless BECKETT_MODEL is set.
To run them:

    BECKETT_MODEL=anthropic:claude-sonnet-4-5 \\
    ANTHROPIC_API_KEY=sk-ant-... \\
    uv run pytest tests/test_live.py -m live -v

They exercise the full Pydantic AI path (not the stub fallback) and verify that
a real model call produces structured, schema-valid output.

IMPORTANT: These tests make real API calls and incur model costs.
Each call is gated by --force so guards are bypassed — only the agent
invocation itself is tested, not guard eligibility.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest

from beckett.loop.deps import RoleDeps
from beckett.loop.runner import run_loop_dryrun, run_single_skill
from beckett.loop.skills.observe import ObserveResult
from beckett.loop.skills.orient_synthesis import SynthesisResult

# ── Fixture helpers ───────────────────────────────────────────────────────────


def _make_live_role(tmp_path: Path, *, role_name: str = "live-test") -> tuple[Path, Path]:
    base = tmp_path / "masks"
    role_dir = base / role_name
    personal_dir = base / "personal"
    role_dir.mkdir(parents=True, exist_ok=True)
    personal_dir.mkdir(parents=True, exist_ok=True)
    (base / "AGENTS.md").write_text("# Global Agents\nThis is a live test role.\n")
    (role_dir / "ROLE.md").write_text(
        textwrap.dedent(f"""\
            # {role_name}

            This is an automated integration test role for Beckett.
            Generate minimal structured output for testing purposes.
        """)
    )
    (role_dir / "CONTEXT.md").write_text("Context: automated test environment.\n")
    (role_dir / "Memory").mkdir()
    (role_dir / "Memory" / "INDEX.md").write_text("| File | Summary | Tags |\n|---|---|---|\n")
    (personal_dir / "SELF.md").write_text("# SELF\nAutomated test persona.\n")
    return base, role_dir


def _make_deps(
    base: Path, role_dir: Path, spec_yaml: str, extra_env: dict | None = None
) -> RoleDeps:
    from beckett.loop.spec import load_loop_spec

    spec_path = role_dir / "loop.yaml"
    spec_path.write_text(spec_yaml)
    spec = load_loop_spec(role_dir)
    model = os.environ.get("BECKETT_MODEL", "")
    env: dict[str, str] = {
        "MASKS_BASE": str(base),
        "BECKETT_MODEL": model,
    }
    if extra_env:
        env.update(extra_env)
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

SYNTHESIS_SPEC = textwrap.dedent("""\
    observe: {entries: []}
    orient:
      entries:
        - id: mask-ooda-orient-synthesis
          agent: mask-ooda-orient-synthesis
    act: {entries: []}
""")

EMAIL_SPEC = textwrap.dedent("""\
    observe:
      entries:
        - id: email-classifier
          agent: email-classifier
    orient: {entries: []}
    act: {entries: []}
""")

ACT_SPEC = textwrap.dedent("""\
    observe: {entries: []}
    orient: {entries: []}
    act:
      entries:
        - id: ooda-act
          agent: ooda-act
""")

BRIEFER_SPEC = textwrap.dedent("""\
    observe: {entries: []}
    orient: {entries: []}
    act:
      entries:
        - id: daily-briefer
          agent: daily-briefer
""")


# ── Live: doctor passes ───────────────────────────────────────────────────────


@pytest.mark.live
def test_live_doctor_passes(tmp_path: Path) -> None:
    """beckett doctor reports all checks passing when model env is configured."""
    from beckett.doctor_cmd import doctor_cmd
    from beckett.loop.skills import register_builtin_skills

    register_builtin_skills()
    base, role_dir = _make_live_role(tmp_path)
    (role_dir / "loop.yaml").write_text(OBSERVE_SPEC)

    import typer
    try:
        doctor_cmd(json_out=False, role_targets=(str(role_dir),))
    except typer.Exit as e:
        assert e.exit_code == 0, "doctor should exit 0 when model env is set"


# ── Live: dry-run shows guard evaluation ─────────────────────────────────────


@pytest.mark.live
def test_live_dryrun_completes(tmp_path: Path) -> None:
    """Dry-run completes without error and returns a valid LoopRunResult."""
    base, role_dir = _make_live_role(tmp_path)
    deps = _make_deps(base, role_dir, OBSERVE_SPEC)

    result = run_loop_dryrun(deps)

    assert result.success is True
    assert result.total_entries == 1
    assert len(result.phases) == 3
    # Dry-run never invokes agents
    for ph in result.phases:
        for sk in ph.skills:
            assert sk.agent_result is None, "dry-run should not invoke agents"


# ── Live: observe agent ───────────────────────────────────────────────────────


@pytest.mark.live
def test_live_observe_agent_returns_valid_schema(tmp_path: Path) -> None:
    """observe agent (forced) returns an ObserveResult-shaped dict."""
    base, role_dir = _make_live_role(tmp_path)
    # Plant an observer marker so the guard has a concrete signal to report
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text(
        "Live test signal: check inbox and calendar.\n"
    )

    deps = _make_deps(base, role_dir, OBSERVE_SPEC)
    sk, _ = run_single_skill(deps, "ooda-observe", force_trigger=True)

    assert sk.error is None, f"agent raised: {sk.error}"
    assert sk.agent_result is not None

    # Validate against ObserveResult schema
    result = ObserveResult.model_validate(sk.agent_result)
    assert isinstance(result.signals_found, int)
    assert isinstance(result.files_written, int)
    assert isinstance(result.sources, list)


@pytest.mark.live
def test_live_observe_writes_memory_file(tmp_path: Path) -> None:
    """observe agent writes at least one file to Memory/Observations/."""
    base, role_dir = _make_live_role(tmp_path)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("Test observation signal.\n")

    deps = _make_deps(base, role_dir, OBSERVE_SPEC)
    run_single_skill(deps, "ooda-observe", force_trigger=True)

    obs_dir = role_dir / "Memory" / "Observations"
    files = list(obs_dir.glob("*.md")) if obs_dir.is_dir() else []
    assert len(files) >= 1, "observe agent should write at least one observation file"
    content = files[0].read_text()
    assert len(content) > 20, "observation file should have meaningful content"


# ── Live: email classifier agent ─────────────────────────────────────────────


@pytest.mark.live
def test_live_email_classifier_returns_valid_schema(tmp_path: Path) -> None:
    """email_classifier agent (forced) returns an EmailClassificationResult-shaped dict."""
    from beckett.loop.skills.email_classifier import EmailClassificationResult

    base, role_dir = _make_live_role(tmp_path)
    deps = _make_deps(base, role_dir, EMAIL_SPEC)

    sk, _ = run_single_skill(deps, "email-classifier", force_trigger=True)

    assert sk.error is None, f"agent raised: {sk.error}"
    assert sk.agent_result is not None

    result = EmailClassificationResult.model_validate(sk.agent_result)
    assert isinstance(result.classified, int)
    assert isinstance(result.skipped, int)
    assert isinstance(result.labels_applied, list)


# ── Live: orient synthesis agent ──────────────────────────────────────────────


@pytest.mark.live
def test_live_synthesis_only_runs_for_personal_role(tmp_path: Path) -> None:
    """Synthesis agent returns 'requires personal role' for non-personal roles."""
    base, role_dir = _make_live_role(tmp_path, role_name="work")
    deps = _make_deps(base, role_dir, SYNTHESIS_SPEC)

    sk, _ = run_single_skill(deps, "mask-ooda-orient-synthesis", force_trigger=True)

    assert sk.error is None
    assert sk.agent_result is not None
    assert sk.agent_result.get("detail") == "requires personal role"


@pytest.mark.live
def test_live_synthesis_personal_role_valid_schema(tmp_path: Path) -> None:
    """Synthesis agent for personal role returns SynthesisResult-shaped dict."""
    base, role_dir = _make_live_role(tmp_path, role_name="personal")
    # Seed a minimal observation file
    obs_dir = role_dir / "Memory" / "Observations"
    obs_dir.mkdir(parents=True, exist_ok=True)
    (obs_dir / "test-obs.md").write_text(
        "# Test Observation\n\n- Timestamp: 2026-04-29\n- Signal: test\n"
    )

    deps = _make_deps(base, role_dir, SYNTHESIS_SPEC)
    sk, _ = run_single_skill(deps, "mask-ooda-orient-synthesis", force_trigger=True)

    assert sk.error is None, f"agent raised: {sk.error}"
    assert sk.agent_result is not None

    result = SynthesisResult.model_validate(sk.agent_result)
    assert isinstance(result.patterns_found, int)
    assert isinstance(result.written, int)
    assert isinstance(result.stale_updated, int)


@pytest.mark.live
def test_live_synthesis_writes_synthesis_log(tmp_path: Path) -> None:
    """Synthesis agent writes .synthesis.log to personal_dir (Rule 7 housekeeping)."""
    base, role_dir = _make_live_role(tmp_path, role_name="personal")
    (role_dir / "Memory" / "Observations").mkdir(parents=True)
    deps = _make_deps(base, role_dir, SYNTHESIS_SPEC)

    run_single_skill(deps, "mask-ooda-orient-synthesis", force_trigger=True)

    log = base / "personal" / ".synthesis.log"
    assert log.is_file(), ".synthesis.log should be written after synthesis run"
    assert "SYNTHESIS" in log.read_text()


# ── Live: act agent ───────────────────────────────────────────────────────────


@pytest.mark.live
def test_live_act_agent_returns_valid_schema(tmp_path: Path) -> None:
    """act agent (forced, no real tasks) returns ActResult-shaped dict."""
    from beckett.loop.skills.act import ActResult

    base, role_dir = _make_live_role(tmp_path)
    deps = _make_deps(base, role_dir, ACT_SPEC)

    sk, _ = run_single_skill(deps, "ooda-act", force_trigger=True)

    assert sk.error is None, f"agent raised: {sk.error}"
    assert sk.agent_result is not None

    result = ActResult.model_validate(sk.agent_result)
    assert isinstance(result.executed, int)
    assert isinstance(result.failed, int)
    assert isinstance(result.task_ids, list)


# ── Live: daily briefer agent ─────────────────────────────────────────────────


@pytest.mark.live
def test_live_daily_briefer_returns_valid_schema(tmp_path: Path) -> None:
    """daily_briefer agent (forced) returns BriefingResult-shaped dict."""
    from beckett.loop.skills.daily_briefer import BriefingResult

    base, role_dir = _make_live_role(tmp_path)
    deps = _make_deps(base, role_dir, BRIEFER_SPEC)

    sk, _ = run_single_skill(deps, "daily-briefer", force_trigger=True)

    assert sk.error is None, f"agent raised: {sk.error}"
    assert sk.agent_result is not None

    result = BriefingResult.model_validate(sk.agent_result)
    assert isinstance(result.delivered, bool)
    assert isinstance(result.sections, list)


# ── Live: full cycle ──────────────────────────────────────────────────────────


@pytest.mark.live
def test_live_full_cycle(tmp_path: Path) -> None:
    """Full observe→orient→act cycle completes; last-run.json is valid."""
    from beckett.loop.runner import run_loop_cycle

    full_spec = textwrap.dedent("""\
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

    base, role_dir = _make_live_role(tmp_path)
    (role_dir / ".ooda-pending").mkdir()
    (role_dir / ".ooda-pending" / "observer.txt").write_text("integration test signal\n")

    deps = _make_deps(base, role_dir, full_spec)
    result = run_loop_cycle(deps, once=True)

    assert result.success is True
    last_run_path = role_dir / ".ooda-state" / "last-run.json"
    assert last_run_path.is_file()

    data = json.loads(last_run_path.read_text())
    assert data["success"] is True
    assert data["total_entries"] == 3
    # Observe should have triggered (marker file was planted)
    triggered_ids = [
        sk["id"]
        for ph in data["phases"]
        for sk in ph["skills"]
        if sk["guard"]["triggered"]
    ]
    assert "ooda-observe" in triggered_ids
