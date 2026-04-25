"""Typer entrypoint for ``beckett``."""

from __future__ import annotations

import typer

from beckett import __version__
from beckett.doctor_cmd import doctor_cmd
from beckett.run_cmd import run_command
from beckett.status_cmd import status_cmd


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


app = typer.Typer(help="Beckett — OODA heartbeat runner and guard monitor.", no_args_is_help=True)


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


@app.command("run")
def run(
    target: str = typer.Argument(
        ...,
        help="Path to Role directory (contains OODA.md), or role name under MASKS_BASE",
    ),
) -> None:
    """Run OODA guards and optionally invoke the heartbeat LLM."""
    run_command(target)


@app.command("doctor")
def doctor(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON report"),
    role_targets: list[str] = typer.Argument(
        default=None,
        help="Optional Role paths or names (default: scan MASKS_BASE)",
    ),
) -> None:
    """Check OODA agendas and guard scripts."""
    rt: tuple[str, ...] = tuple(role_targets) if role_targets else ()
    doctor_cmd(json_out=json_out, role_targets=rt)


@app.command("status")
def status(
    role_targets: list[str] = typer.Argument(
        default=None,
        help="Optional Role paths or names (default: scan MASKS_BASE)",
    ),
) -> None:
    """Show last OODA_OK and latest log line per Role."""
    rt: tuple[str, ...] = tuple(role_targets) if role_targets else ()
    status_cmd(role_targets=rt)
