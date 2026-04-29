"""``beckett install`` — non-destructively create loop.yaml for each role."""

from __future__ import annotations

from pathlib import Path

import typer

from beckett.paths import resolve_base_path
from beckett.role_path import resolve_role_dir
from beckett.roles import iter_role_dirs

# ── Default loop.yaml template ────────────────────────────────────────────────

_DEFAULT_YAML = """\
# Beckett loop configuration.
# See: beckett doctor    — validate this file and the tool registry
#      beckett loop --dry-run  — preview which guards would fire
#
# Each entry maps to a registered guard + agent pair.
# Remove entries your role doesn't need.

observe:
  entries:
    - id: ooda-observe
      agent: ooda-observe

orient:
  entries:
    - id: email-classifier
      agent: email-classifier
    # Uncomment for the personal role only:
    # - id: mask-ooda-orient-synthesis
    #   agent: mask-ooda-orient-synthesis

act:
  entries:
    - id: daily-briefer
      agent: daily-briefer
    - id: ooda-act
      agent: ooda-act

# Active-hours gate (daemon mode only). Guards are skipped outside this window.
# Remove this line to run at any hour.
active_hours: "09:00-17:00"

# Daemon loop interval. Overridden by --interval or BECKETT_LOOP_INTERVAL.
interval_minutes: 15
"""

# ── Install logic ─────────────────────────────────────────────────────────────


def _install_one(role_dir: Path, *, force: bool, dry_run: bool) -> tuple[str, str]:
    """Write loop.yaml for a single role. Returns (action, note)."""
    spec_path = role_dir / "loop.yaml"

    if spec_path.exists() and not force:
        return "skipped", "loop.yaml already exists (--force to overwrite)"

    action = "updated" if spec_path.exists() else "created"
    if not dry_run:
        spec_path.write_text(_DEFAULT_YAML, encoding="utf-8")
    return action, str(spec_path)


# ── CLI command ───────────────────────────────────────────────────────────────


def install_cmd(
    role_targets: tuple[str, ...] = (),
    *,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Non-destructively create loop.yaml for each role from the default template.

    Skips roles that already have loop.yaml unless --force is passed.
    After running, edit each loop.yaml to match your role's needs, then run
    ``beckett doctor`` to validate.
    """
    if role_targets:
        role_dirs = [resolve_role_dir(t) for t in role_targets]
    else:
        role_dirs = list(iter_role_dirs(resolve_base_path()))

    if not role_dirs:
        typer.echo("No role directories found. Is MASKS_BASE configured?")
        raise typer.Exit(0)

    if dry_run:
        typer.secho("[DRY RUN] no files will be written", fg=typer.colors.YELLOW)
        typer.echo("")

    rows: list[tuple[str, str, str]] = []
    for role_dir in role_dirs:
        action, note = _install_one(role_dir, force=force, dry_run=dry_run)
        rows.append((role_dir.name, action, note))

    max_role = max(len(r[0]) for r in rows)
    typer.echo(f"{'ROLE':<{max_role + 2}} {'ACTION':<10} NOTE")
    for role, action, note in rows:
        color = {"created": typer.colors.GREEN, "updated": typer.colors.CYAN}.get(action)
        line = f"{role:<{max_role + 2}} {action:<10} {note}"
        if color:
            typer.secho(line, fg=color)
        else:
            typer.echo(line)

    if dry_run:
        typer.echo("\nRe-run without --dry-run to write the files.")
        return

    created = sum(1 for _, a, _ in rows if a in ("created", "updated"))
    if created:
        typer.echo(
            "\nNext steps:\n"
            "  1. Edit each loop.yaml to match your role (remove entries you don't need).\n"
            "  2. beckett doctor          — validate config and registry\n"
            "  3. beckett loop --dry-run  — preview guard outcomes without spending tokens\n"
            "  4. beckett loop --once     — run one full cycle"
        )
