# Beckett — design

Beckett is a Pirandello-aware **loop runtime** implemented in Python with
typed `LoopSpec` configuration, guard functions, and native skill agents.

## Architecture

- Pirandello (`masks`) owns role provisioning, hooks, and memory indexing.
- Beckett owns non-interactive loop execution over one or more roles.
- Runtime is process-local (`beckett loop`) with built-in interval handling.

## Runtime contract

For each loop cycle and each role target:

1. Resolve role directory from explicit target or `MASKS_BASE` discovery.
2. Merge environment: `os.environ` -> `parent(role)/.env` -> `role/.env`.
3. Load `LoopSpec` from role-local `loop.yaml` / `loop.json` / `loop.py`.
4. Execute phases in order: `observe` -> `orient` -> `act`.
5. For each phase entry:
   - run guard function (`GuardOutcome`)
   - run agent only when guard triggers
6. Write `<role>/.ooda-state/last-run.json`.
7. Stage and commit role changes (`git add -A`, conditional commit).

## Memory contract

- Canonical writes go to filesystem `Memory/**/*.md`.
- Semantic reads use `mcp_memory_service` storage directly.
- MCP memory server is not used as canonical storage.

## CLI surface

- `beckett roles`
- `beckett doctor`
- `beckett status`
- `beckett loop`

## Environment notes

- Base path defaults: `MASKS_BASE` env, then Desktop `.env` (`MASKS_BASE=`), then `~/Desktop`.
- Role-local `.env` remains highest-precedence file layer.
