"""``beckett status`` — latest loop run summary per role."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from beckett.paths import resolve_base_path
from beckett.role_path import resolve_role_dir
from beckett.roles import iter_role_dirs


def _read_last_run(role_path: Path) -> dict | None:
    runf = role_path / ".ooda-state" / "last-run.json"
    if not runf.is_file():
        return None
    try:
        return json.loads(runf.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def status_cmd(role_targets: tuple[str, ...] = ()) -> None:
    if role_targets:
        role_paths = [resolve_role_dir(t) for t in role_targets]
    else:
        role_paths = list(iter_role_dirs(resolve_base_path()))

    typer.echo(f"{'ROLE':<16} {'LAST_RUN':<26} {'TRIGGERED':<12} {'SUCCESS':<8}")
    for role_path in role_paths:
        name = role_path.name
        data = _read_last_run(role_path)
        if not data:
            typer.echo(f"{name:<16} {'never':<26} {'0/0':<12} {'no':<8}")
            continue
        last_run = str(data.get("finished_at", "never"))[:26]
        trig = f"{data.get('triggered_count', 0)}/{data.get('total_entries', 0)}"
        success = "yes" if bool(data.get("success", False)) else "no"
        typer.echo(f"{name:<16} {last_run:<26} {trig:<12} {success:<8}")
