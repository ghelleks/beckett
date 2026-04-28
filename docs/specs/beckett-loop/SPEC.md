# Beckett Loop Specification

## Scope

`beckett loop` is the canonical headless runtime for Pirandello roles.
It replaces Prefect orchestration and the legacy `OODA.md`-driven heartbeat.

## Configuration

- Loop configuration must be provided by `LoopSpec`.
- Loading precedence:
  1. `--spec <path>`
  2. `<role>/loop.yaml` or `<role>/loop.yml`
  3. `<role>/loop.json`
  4. `<role>/loop.py` exposing `LOOP_SPEC`
- `OODA.md` is not supported as runtime input.

## Execution Model

- Roles:
  - With `--role-target`: run one role.
  - Without `--role-target`: discover all role directories under `MASKS_BASE`.
- For each role and each phase (`observe`, `orient`, `act`) in order:
  - Evaluate guard function (`GuardOutcome`).
  - Run agent function only when guard is triggered.
- Continue processing remaining roles even if one role fails.

## Exit Codes

- `0`: no fatal errors and no partial agent failures.
- `1`: one or more fatal configuration/dependency errors.
- `2`: no fatals, but one or more agent execution failures.

## Memory Contract

- Canonical memory store is markdown files under `<role>/Memory/`.
- Semantic search uses `mcp_memory_service` library against `MCP_MEMORY_DB_PATH`.
- Runtime never writes to MCP memory server as canonical state.
- End-of-cycle commit policy:
  - Stage all role changes (`git add -A`).
  - Commit if staged changes exist.
  - Commit may occur even on partial-failure cycles.
- Post-commit hooks update memory index (`masks index`) when memory files changed.

## CLI Surface

- `beckett loop`
- `beckett loop --role-target <name>`
- `beckett loop --once`
- `beckett loop --interval <duration>`
- `beckett loop --spec <path>` (requires `--role-target`)

## Supporting Commands

- `beckett doctor` validates:
  - `loop_spec`
  - `registry`
  - `model_env` (warning-only)
- `beckett roles` reports spec source per role.
- `beckett status` reads `<role>/.ooda-state/last-run.json`.
