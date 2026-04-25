# Beckett — design

Beckett is the **non-interactive OODA runner** for Pirandello-style Role workspaces. It lives in a separate repository from **Pirandello** (the `masks` CLI): Pirandello owns setup, hooks, memory indexing, sync, reflect, and reference refresh; **Beckett** owns `OODA.md` parsing, guard execution, `.ooda.log`, and optional heartbeat LLM invocation.

## Relationship to Pirandello

- **Role directories** are created and maintained with `masks setup`, `masks add-role`, etc. Each Role is a git repo under `MASKS_BASE`.
- **Beckett** reads `OODA.md` and role `.env` from that tree. It does not install Cursor hooks or run `masks index`.
- Install both CLIs: `uv tool install` from Pirandello `cli/` and Beckett `cli/`.

## OODA

Each Role that runs autonomous background work has an `OODA.md`: signals, agenda (Observe / Orient / Act), and exclusions. Skills stay generic; the Role supplies ordering and configuration.

The loop is intended to run on a fixed cadence (e.g. every 15 minutes on weekdays). Time-specific skills (e.g. `daily-briefer` near 06:45) **self-guard** inside their shell scripts; `beckett run` does not parse times from markdown.

### Pre-flight guards

Each cycle runs all guards listed in `OODA.md`, in order, with no early exit. Guards are fast shell scripts: **exit 0** means “there is work for the LLM agenda”; **non-zero** means skip. If **every** guard is non-zero, Beckett logs a line containing `OODA_OK` and does not start an LLM.

Guard implementations ship under `guards/` in this repo and are bundled into the `beckett` wheel as `beckett/_data/guards/`. Resolution uses `resolve_framework_root()` (bundled `_data/`), never a filesystem walk to find a dev checkout.

### LLM invocation

If any guard exits 0, Beckett runs one subprocess with **only** the UTF-8 text of `OODA.md` on stdin. Default command: `claude --print --output-format text`. Override with `BECKETT_LLM_CMD` (or legacy `MASKS_LLM_CMD`) in the merged environment.

### Write routing (policy)

Observations and synthesis destinations follow the same custody rules as Pirandello (work vs personal Memory, synthesis to `personal/Memory/`). Beckett does not enforce writes; guards and the LLM session honor your skills and `OODA.md` text.

### `OODA.md` shape

Use the template in `templates/OODA.md` (also bundled). Numbered items under `### Observe`, `### Orient`, and `### Act` must be kebab-case skill slugs matching `guards/<slug>.sh` in this repository (or your extended guard set if you fork Beckett).

## CLI commands

| Command | Purpose |
|--------|---------|
| `beckett run <path-or-name>` | Guards + optional LLM; logs to `<role_dir>/.ooda.log` |
| `beckett doctor [--json] [paths...]` | Agenda parse + guard file presence under each role |
| `beckett status [paths...]` | Last `OODA_OK` / last log line per role (or scan `MASKS_BASE`) |

## Environment

See `cli/beckett/_data/.env.example`. Role `.env` typically sets `GWS_PROFILE` and API-related keys for guards; base `.env` sets `MASKS_BASE` and optional `BECKETT_LLM_CMD`.

## Cron

```cron
*/15 * * * 1-5 beckett run "$MASKS_BASE/work" 2>>"$MASKS_BASE/work/.ooda.log"
```

Use an explicit path if `MASKS_BASE` is not set in the cron environment:

```cron
*/15 * * * 1-5 beckett run /Users/you/Desktop/masks-base/work 2>>/Users/you/Desktop/masks-base/work/.ooda.log
```
