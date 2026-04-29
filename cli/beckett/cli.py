"""Typer entrypoint for ``beckett``."""

from __future__ import annotations

import json

import typer

from beckett import __version__
from beckett.doctor_cmd import doctor_cmd
from beckett.install_cmd import install_cmd
from beckett.loop.runner import (
    LoopRunResult,
    SkillRunResult,
    run_loop_daemon,
    run_loop_dryrun,
    run_loop_once,
    run_single_skill,
)
from beckett.roles_cmd import roles_cmd
from beckett.status_cmd import status_cmd


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


app = typer.Typer(help="Beckett — Pydantic AI loop runner for Pirandello roles.", no_args_is_help=True)


@app.callback()
def _main(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_cb,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Beckett CLI."""


@app.command("install")
def install(
    role_targets: list[str] = typer.Argument(
        default=None,
        help="Optional Role paths or names (default: scan MASKS_BASE)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing loop.yaml files.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be created without writing any files.",
    ),
) -> None:
    """Create or update loop.yaml for each role (non-destructive by default).

    Migrates from OODA.md when present; falls back to a default template.
    Skips roles that already have loop.yaml unless --force is passed.

    Examples:

      beckett install                     # all roles under MASKS_BASE

      beckett install work                # one role only

      beckett install --dry-run           # preview without writing

      beckett install --force             # overwrite existing loop.yaml files
    """
    rt: tuple[str, ...] = tuple(role_targets) if role_targets else ()
    install_cmd(rt, force=force, dry_run=dry_run)


@app.command("doctor")
def doctor(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON report"),
    role_targets: list[str] = typer.Argument(
        default=None,
        help="Optional Role paths or names (default: scan MASKS_BASE)",
    ),
) -> None:
    """Check loop specs, tool registry coverage, and model environment."""
    rt: tuple[str, ...] = tuple(role_targets) if role_targets else ()
    doctor_cmd(json_out=json_out, role_targets=rt)


@app.command("roles")
def roles(
    role_targets: list[str] = typer.Argument(
        default=None,
        help="Optional Role paths or names (default: scan MASKS_BASE)",
    ),
) -> None:
    """List role directories and loop spec availability."""
    rt: tuple[str, ...] = tuple(role_targets) if role_targets else ()
    roles_cmd(role_targets=rt)


@app.command("status")
def status(
    role_targets: list[str] = typer.Argument(
        default=None,
        help="Optional Role paths or names (default: scan MASKS_BASE)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show full per-phase and per-skill breakdown from last-run.json.",
    ),
) -> None:
    """Show latest loop run summary per role."""
    rt: tuple[str, ...] = tuple(role_targets) if role_targets else ()
    status_cmd(role_targets=rt, verbose=verbose)


def _print_dryrun(result: LoopRunResult) -> None:
    """Format a dry-run result as a guard trigger table."""
    typer.echo(f"[DRY RUN] role={result.role}  {result.started_at}")
    for phase in result.phases:
        typer.echo(f"\nPhase: {phase.phase}")
        if not phase.skills:
            typer.echo("  (no entries)")
            continue
        for sk in phase.skills:
            icon = "▶" if sk.guard.triggered else "·"
            state = "TRIGGER" if sk.guard.triggered else ("SKIP   " if not sk.skipped else "SKIP(X)")
            typer.echo(f"  {icon} {sk.id:<32} {state}  {sk.guard.detail!r}")
    typer.echo(
        f"\nSummary: {result.triggered_count} would trigger / {result.total_entries} total"
    )


def _print_skill_result(skill_id: str, sk: SkillRunResult, committed: bool) -> None:
    """Format a single-skill run result."""
    icon = "▶" if sk.guard.triggered else "·"
    typer.echo(f"Skill: {skill_id}")
    typer.echo(f"Guard:  {icon} {'TRIGGER' if sk.guard.triggered else 'SKIP'}  {sk.guard.detail!r}")
    if sk.skipped:
        typer.echo("Agent:  SKIPPED (not in registry)")
    elif not sk.guard.triggered:
        typer.echo("Agent:  not run (guard did not trigger)")
    elif sk.error:
        typer.secho(f"Agent:  ERROR — {sk.error}", fg=typer.colors.RED, err=True)
    else:
        result_str = json.dumps(sk.agent_result, indent=2) if sk.agent_result else "{}"
        typer.echo(f"Agent:  OK\n{result_str}")
    typer.echo(f"Committed: {'yes' if committed else 'no'}")


@app.command("loop")
def loop(
    role_target: str | None = typer.Option(
        None,
        "--role-target",
        help="Optional role path or name. Omit to run all roles under MASKS_BASE.",
    ),
    once: bool = typer.Option(False, "--once", help="Run one cycle and exit."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Evaluate guards only — print what would trigger without running agents.",
    ),
    skill: str | None = typer.Option(
        None,
        "--skill",
        help="Run a single skill by entry ID (implies --once). Requires --role-target.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="With --skill: run the agent even if the guard does not trigger.",
    ),
    interval: str = typer.Option("15m", "--interval", help="Loop interval (e.g. 5m, 30s, 1h)."),
    spec: str | None = typer.Option(
        None,
        "--spec",
        help="Optional LoopSpec path (yaml/json/python). Requires --role-target.",
    ),
) -> None:
    """Run the Beckett loop daemon, a single cycle, or a single skill.

    Examples:

      beckett loop --once --role-target work

      beckett loop --dry-run --role-target work

      beckett loop --skill ooda-observe --role-target work

      beckett loop --skill ooda-observe --role-target work --force
    """
    from beckett.loop.deps import build_role_deps
    from beckett.loop.spec import LoopConfigError

    if skill:
        if not role_target:
            typer.secho("--skill requires --role-target", err=True, fg=typer.colors.RED)
            raise typer.Exit(2)
        try:
            deps = build_role_deps(role_target, explicit_spec=spec)
            sk, committed = run_single_skill(deps, skill, force_trigger=force)
            _print_skill_result(skill, sk, committed)
        except LoopConfigError as exc:
            typer.secho(str(exc), err=True, fg=typer.colors.RED)
            raise typer.Exit(1) from exc
        return

    if dry_run:
        from pathlib import Path
        targets = [role_target] if role_target else None
        if targets is None:
            from beckett.paths import resolve_base_path
            from beckett.roles import iter_role_dirs
            targets = [str(p) for p in iter_role_dirs(resolve_base_path())]
        for target in targets:
            try:
                deps = build_role_deps(target, explicit_spec=spec)
                result = run_loop_dryrun(deps)
                _print_dryrun(result)
            except LoopConfigError as exc:
                typer.secho(f"[FAIL] {Path(target).name}: {exc}", err=True, fg=typer.colors.RED)
        return

    if once:
        run_loop_once(role_target=role_target, spec_path=spec)
        return
    run_loop_daemon(role_target=role_target, interval=interval, spec_path=spec)
