"""Resolve CLI target to a Role directory (path-first, optional MASKS_BASE shorthand)."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from beckett.paths import resolve_base_path


def resolve_role_dir(target: str) -> Path:
    """
    Primary: existing directory path (absolute, ~, or relative to cwd).
    Fallback: bare name with no path separators → ``MASKS_BASE/<name>`` if that directory exists.
    """
    raw = target.strip()
    if not raw:
        typer.secho("Role directory path or role name is required.", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)

    expanded = Path(raw).expanduser()
    if expanded.is_dir():
        return expanded.resolve()

    if os.sep not in raw.rstrip(os.sep) and "/" not in raw:
        base = resolve_base_path()
        cand = (base / raw).resolve()
        if cand.is_dir():
            return cand

    typer.secho(
        f"Not a directory and not found under MASKS_BASE: {raw}\n"
        f"  (resolved tried: {expanded.resolve()!s} and {resolve_base_path() / raw!s})",
        err=True,
        fg=typer.colors.RED,
    )
    raise typer.Exit(2)
