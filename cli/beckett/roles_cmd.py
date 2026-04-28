"""``beckett roles`` — list role directories under MASKS_BASE."""

from __future__ import annotations

from pathlib import Path

import typer

from beckett.loop.spec import detect_spec_source
from beckett.paths import resolve_base_path
from beckett.role_path import resolve_role_dir
from beckett.roles import iter_role_dirs


def _iter_targets(role_targets: tuple[str, ...]) -> list[Path]:
    if role_targets:
        return [resolve_role_dir(t) for t in role_targets]
    return list(iter_role_dirs(resolve_base_path()))


def roles_cmd(role_targets: tuple[str, ...] = ()) -> None:
    """List role directories and LoopSpec availability."""
    rows: list[tuple[str, str, str]] = []
    for role_dir in _iter_targets(role_targets):
        status, _ = detect_spec_source(role_dir)
        rows.append((role_dir.name, str(role_dir), status))

    if not rows:
        typer.echo("No role directories found.")
        raise typer.Exit(0)

    typer.echo(f"{'ROLE':<16} {'SPEC':<22} {'PATH'}")
    for role, path, status in rows:
        typer.echo(f"{role:<16} {status:<22} {path}")
