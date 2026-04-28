"""Typer entrypoint for ``beckett``."""

from __future__ import annotations

import typer

from beckett import __version__
from beckett.doctor_cmd import doctor_cmd
from beckett.loop.runner import run_loop_daemon, run_loop_once
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
) -> None:
    """Show latest loop run summary per role."""
    rt: tuple[str, ...] = tuple(role_targets) if role_targets else ()
    status_cmd(role_targets=rt)


@app.command("loop")
def loop(
    role_target: str | None = typer.Option(
        None,
        "--role-target",
        help="Optional role path or name. Omit to run all roles under MASKS_BASE.",
    ),
    once: bool = typer.Option(False, "--once", help="Run one cycle and exit."),
    interval: str = typer.Option("15m", "--interval", help="Loop interval (e.g. 5m, 30s, 1h)."),
    spec: str | None = typer.Option(
        None,
        "--spec",
        help="Optional LoopSpec path (yaml/json/python). Requires --role-target.",
    ),
) -> None:
    """Run the Beckett loop daemon or a single cycle."""
    if once:
        run_loop_once(role_target=role_target, spec_path=spec)
        return
    run_loop_daemon(role_target=role_target, interval=interval, spec_path=spec)
