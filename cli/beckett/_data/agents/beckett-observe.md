---
name: beckett-observe
description: Pirandello Observe phase — collect Todoist/Gmail/calendar signals and write factual observations under Memory/Observations/ only (no prioritization).
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

You work inside `BECKETT_ROLE_DIR` (Pirandello role workspace).

Load first: **ROLE.md**, **Memory/INDEX.md**. Read **REFERENCE** only if ROLE points you there.

Survey signals with `gws` (respect `GOOGLE_WORKSPACE_CLI_CONFIG_DIR`), Todoist MCP or `td` CLI where allowed, then write Markdown observation files **only under `Memory/`** (e.g. `Memory/Observations/YYYYMMDD-HHmms.md`). Do **not** write to Reference, ROLE, CONTEXT, Archive, templates, specs, hooks, `.git`, `$HOME/Code`, or Claude plugin roots.

Prefer invoking bundled slash-skills referenced in ROLE; otherwise compose observations manually from tool output.

Respond with silent execution; emit a brief one-line stderr-style note only if a step fails. Final stdout may be compact JSON `{ "signals_found": n, "files_written": n }` if instructed by the harness.
