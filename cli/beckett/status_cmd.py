"""``beckett status`` — OODA log summary per Role."""

from __future__ import annotations

from pathlib import Path

import typer

from beckett.paths import resolve_base_path
from beckett.role_path import resolve_role_dir
from beckett.roles import iter_role_dirs


def _last_ooda_ok(role_path: Path) -> str:
    logf = role_path / ".ooda.log"
    if not logf.is_file():
        return "never"
    lines = logf.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        if "OODA_OK" in line:
            return line.strip()[:80]
    return "never"


def _last_run_line(role_path: Path) -> str:
    logf = role_path / ".ooda.log"
    if not logf.is_file():
        return "never"
    lines = logf.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return "never"
    return lines[-1].strip()[:100]


def status_cmd(role_targets: tuple[str, ...] = ()) -> None:
    if role_targets:
        role_paths = [resolve_role_dir(t) for t in role_targets]
    else:
        role_paths = list(iter_role_dirs(resolve_base_path()))

    typer.echo(f"{'ROLE':<16} {'LAST_OODA_OK':<42} {'LAST_LOG_LINE':<100}")
    for role_path in role_paths:
        name = role_path.name
        typer.echo(
            f"{name:<16} {_last_ooda_ok(role_path):<42} {_last_run_line(role_path):<100}"
        )
