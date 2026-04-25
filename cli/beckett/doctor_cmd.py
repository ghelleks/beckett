"""``beckett doctor`` — OODA agenda and guard health."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer

from beckett.ooda_parse import extract_agenda_skills
from beckett.paths import resolve_base_path, resolve_framework_root
from beckett.role_path import resolve_role_dir
from beckett.roles import iter_role_dirs


def _collect_role_dirs(explicit: tuple[str, ...]) -> list[Path]:
    if explicit:
        return [resolve_role_dir(t) for t in explicit]
    return list(iter_role_dirs(resolve_base_path()))


def doctor_cmd(json_out: bool = False, role_targets: tuple[str, ...] = ()) -> None:
    """Validate OODA.md agendas and bundled guard scripts."""
    fw = resolve_framework_root()
    roles = _collect_role_dirs(role_targets)
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, msg: str, status: str | None = None) -> None:
        st = status or ("pass" if ok else "fail")
        checks.append({"id": cid, "status": st, "message": msg})

    bad_ooda: list[str] = []
    for r in roles:
        skills = extract_agenda_skills(r / "OODA.md")
        if not skills:
            bad_ooda.append(r.name)
    ok1 = not bad_ooda
    msg1 = "all roles parseable" if ok1 else f"missing or empty agenda: {', '.join(bad_ooda)}"
    add("ooda_agenda", ok1, msg1)

    all_skills: set[str] = set()
    for r in roles:
        all_skills.update(extract_agenda_skills(r / "OODA.md"))
    guards_dir = fw / "guards"
    bad_guards: list[str] = []
    if not guards_dir.is_dir():
        bad_guards.append("guards/ directory missing")
    else:
        for s in sorted(all_skills):
            g = guards_dir / f"{s}.sh"
            if not g.is_file():
                bad_guards.append(f"missing {s}.sh")
            elif not os.access(g, os.X_OK):
                bad_guards.append(f"{s}.sh not executable")
    ok2 = not bad_guards
    msg2 = "all guards present" if ok2 else "; ".join(bad_guards)
    add("guards_executable", ok2, msg2)

    blocking_ok = all(c["status"] == "pass" for c in checks)

    if json_out:
        out = {"ok": blocking_ok, "checks": checks}
        typer.echo(json.dumps(out, indent=2))
    else:
        for c in checks:
            tag = c["status"].upper()
            typer.echo(f"[{tag}] {c['id']}: {c['message']}")

    if not blocking_ok:
        raise typer.Exit(1)
