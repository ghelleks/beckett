# SDD Spec: `beckett run` — Heartbeat Runner

**Context:** See [docs/design.md](../../design.md). This spec covers the OODA heartbeat runner: cron-friendly pre-flight guards and conditional LLM invocation.

**Deliverables:** `cli/beckett/run_cmd.py`, bundled `beckett/_data/guards/` with pre-flight guard contract.

---

## Requirements

### Hard constraints

1. Entry point: `beckett run <target>`. **Primary:** `<target>` is a filesystem path to the Role directory (contains `OODA.md`). **Optional shorthand:** bare name with no path separators → resolve `MASKS_BASE/<name>` (same `MASKS_BASE` / `~/Desktop` fallback as Pirandello `masks`). **Existing directory wins** over shorthand when both could apply.
2. `MASKS_BASE` is read for shorthand resolution only; Role paths are otherwise independent of `$PWD` except when `<target>` is a relative path (resolved from cwd).
3. Before guard execution, merge `os.environ` with keys from `parent(role_dir)/.env` then `role_dir/.env` (role wins), matching Pirandello `merge_env_for_role` semantics.
4. Reads `role_dir/OODA.md` for the agenda (`### Observe`, `### Orient`, `### Act`, numbered skill slugs).
5. For each skill, executes `resolve_framework_root() / "guards" / <skill>.sh` (bundled in the installed wheel). Guards run in agenda order; **all** guards always run (no early exit).
6. Guard contract: exit **0** = work to do (may trigger LLM); non-zero = skip. Fast, deterministic, no LLM inside guards; 5s timeout per guard.
7. If **all** guards non-zero: append log line including `OODA_OK` to `role_dir/.ooda.log`, exit 0, no LLM.
8. If **any** guard exits 0: invoke LLM with **only** `OODA.md` body as stdin (no SELF.md, ROLE.md, CONTEXT.md, indexes).
9. Every run logs timestamp, guard exit summary, trigger yes/no, LLM yes/no to `role_dir/.ooda.log`.
10. Missing `OODA.md`: log warning, exit 0.
11. Missing or non-executable guard: warn in log, treat as failed, continue.
12. Cron example: `*/15 * * * 1-5 beckett run "$MASKS_BASE/work" 2>> "$MASKS_BASE/work/.ooda.log"`

### Guard contract

Same as Pirandello `masks run` era: see [docs/design.md](../../design.md) guard section. `MASKS_ROLE`, `MASKS_ROLE_DIR`, `MASKS_BASE`, `MASKS_OODA_PATH`, and `BECKETT_*` mirrors are set in the subprocess environment for scripts.

### Soft constraints

- LLM command: `BECKETT_LLM_CMD` preferred; `MASKS_LLM_CMD` honored for migration. Debug: `BECKETT_LLM_DEBUG` or `MASKS_LLM_DEBUG=1`.
- Time-of-day logic lives only in guard scripts.
- **gws:** guards use merged env (`GWS_PROFILE` from role `.env`); OAuth lives in gws config, not Beckett.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| B-01 | Role from path | Primary resolution uses explicit Role directory path, not `$PWD` as implicit role |
| B-02 | Env sourcing order | `parent/.env` then `role_dir/.env` merged into env (role overrides base) |
| B-03 | OODA.md parse | Numbered skills under Observe/Orient/Act extracted in document order |
| B-04 | Guard order | All guards run in OODA.md order |
| B-05 | Any-pass trigger | One guard exit 0 triggers LLM |
| B-06 | All-fail no-op | All non-zero → `OODA_OK` in log, no LLM |
| B-07 | OODA sole context | LLM stdin is OODA.md text only |
| B-08 | Log completeness | Each run appends summary line |
| B-09 | Missing guard graceful | Missing/non-exec guard logged, treated as fail, continue |
| B-10 | Missing OODA graceful | Warning log, exit 0 |
