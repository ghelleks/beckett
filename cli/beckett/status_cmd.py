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


def _format_agent_result(result: dict | None) -> str:
    if not result:
        return ""
    pairs = []
    for k, v in result.items():
        if k == "error":
            continue
        if isinstance(v, list):
            pairs.append(f"{k}={len(v)}")
        elif isinstance(v, bool):
            pairs.append(f"{k}={'yes' if v else 'no'}")
        else:
            pairs.append(f"{k}={v}")
    return "  ".join(pairs)


def _print_verbose(name: str, data: dict) -> None:
    last_run = str(data.get("finished_at", "never"))[:26]
    trig = f"{data.get('triggered_count', 0)}/{data.get('total_entries', 0)}"
    success = "yes" if data.get("success") else "no"
    committed = "yes" if data.get("committed") else "no"

    typer.echo(f"\nROLE: {name}")
    typer.echo(f"  Last run:  {last_run}")
    typer.echo(f"  Triggered: {trig}   Success: {success}   Committed: {committed}")

    for phase in data.get("phases", []):
        phase_name = phase.get("phase", "?")
        skills = phase.get("skills", [])
        typer.echo(f"\n  Phase: {phase_name}")
        if not skills:
            typer.echo("    (no entries)")
            continue
        for sk in skills:
            sid = sk.get("id", "?")
            guard = sk.get("guard", {})
            triggered = guard.get("triggered", False)
            detail = guard.get("detail", "")
            skipped = sk.get("skipped", False)
            error = sk.get("error")
            agent_result = sk.get("agent_result")

            if skipped:
                icon, state = "·", "SKIP(X)"
            elif triggered:
                icon, state = "▶", "TRIGGER"
            else:
                icon, state = "·", "SKIP   "

            line = f"    {icon} {sid:<32} {state}  {detail!r}"
            if error:
                line += f"  ERROR={error[:60]}"
            elif agent_result:
                formatted = _format_agent_result(agent_result)
                if formatted:
                    line += f"  {formatted}"
            typer.echo(line)


def status_cmd(role_targets: tuple[str, ...] = (), *, verbose: bool = False) -> None:
    if role_targets:
        role_paths = [resolve_role_dir(t) for t in role_targets]
    else:
        role_paths = list(iter_role_dirs(resolve_base_path()))

    if verbose:
        for role_path in role_paths:
            name = role_path.name
            data = _read_last_run(role_path)
            if not data:
                typer.echo(f"\nROLE: {name}\n  (no run data)")
                continue
            _print_verbose(name, data)
        return

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
