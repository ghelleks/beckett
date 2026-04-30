# Beckett Loop Scenarios

**Companion spec:** `docs/specs/beckett-loop/SPEC.md`  
**Date:** 2026-04-30

---

## S1: Valid single-role one-shot

- Role has `loop.yaml` with at least one entry.
- All registry entries resolve.
- At least one guard triggers.
- `beckett loop --once --role-target work` exits `0`.
- `work/.beckett-state/last-run.json` exists and contains `triggered_count >= 1` and `success: true`.

---

## S2: OODA-only role fails

- Role has `OODA.md` but no `loop.*`.
- `beckett doctor` reports `loop_spec: fail`.
- `beckett loop --once --role-target <role>` exits `1`.

---

## S3: Multi-role continue-on-failure

- Three roles discovered under `MASKS_BASE`.
- One role has an invalid spec (fatal config error).
- The remaining two roles still execute.
- Process exits `1`.

---

## S4: Partial agent failure

- Spec loads and registry resolves.
- One agent function raises a runtime error.
- Remaining entries in all phases continue.
- Process exits `2`.
- Successful outputs from other entries are still committed.
- `last-run.json` shows `success: false`; the failing skill shows `error` field set.

---

## S5: No changes — no commit

- No guard triggers and no memory files are modified.
- Loop run completes without creating a new git commit.
- `last-run.json` shows `committed: false`.

---

## S6: Memory write-local enforcement

- A skill's agent calls `write_memory_file` with a path that escapes `role_dir/Memory/` (e.g. `../../other-role/Memory/hack`).
- The `write_memory` Python function raises `MemoryWriteError`.
- The write is rejected; no file is created outside the role's memory root.

---

## S7: Personal synthesis write policy

- `beckett-orient-synthesis` running in the `personal` role writes to `personal/Memory/Synthesis/` using `allow_personal_synthesis=True`.
- The same write attempted from a non-personal role or without `allow_personal_synthesis=True` is rejected.

---

## S8: Status output

- `last-run.json` exists: `beckett status` shows run timestamp, triggered/total count, and success status in tabular format.
- Missing `last-run.json`: status row shows `never` and `0/0`.

---

## S9: Dry-run — guard table, no agents

- Role has a valid `loop.yaml` with two entries.
- Observer marker file is present (would trigger `beckett-observe`).
- `BECKETT_LLM_CMD` is set to a sentinel-writing script.
- `beckett loop --dry-run --role-target <role>` runs.

Expected outcomes:

- Exit code `0`.
- Output contains `Phase: observe`, `▶ beckett-observe … TRIGGER`, `·` line for skipped entries as applicable.
- Output contains counts such as `1 would trigger / 2 total`.
- The sentinel file from `BECKETT_LLM_CMD` is **not created** (agents never invoked).
- `last-run.json` is **not written** (dry-run makes no side effects).

---

## S10: Per-skill invocation with --force

- `BECKETT_LLM_CMD` is set to a stub that writes a sentinel and prints `OK`.
- `beckett loop --skill beckett-observe --role-target <role> --force`.
- The `beckett-observe` guard does not fire (no marker, no unread email).

Expected outcomes:

- Exit code `0`.
- Guard result shows `TRIGGER` with `forced (was: …)` in detail.
- Agent runs: sentinel file is created.
- Output contains `Skill: beckett-observe`, `Guard: ▶ TRIGGER`, and `Agent: OK`.
- `committed: yes/no` is reported.

Without `--force`, if guard does not trigger:

- Output shows `not run (guard did not trigger)`.
- Sentinel file is **not created**.

---

## S11: OpenShell wraps subprocess

- `BECKETT_OPENSHELL_POLICY=/path/to/policy.yaml` is set and OpenShell is on PATH.
- `beckett loop --skill beckett-observe --role-target <role> --force`.
- `invoke_claude` constructs argv as `openshell run --policy /path/to/policy.yaml -- claude --print --output-format text`.

When OpenShell is **not on PATH** but policy is set:

- `beckett doctor` reports `openshell: warn` with message `openshell binary not found on PATH`.
- `beckett loop` still runs; `invoke_claude` falls back to unsandboxed invocation.
- No error exit.

---

## S12: Two-pass trigger context

- Phase `observe` has two entries that both guard-trigger in the fixture (e.g. `beckett-observe` marker present and a second entry whose guard is satisfied).
- Both guards trigger.
- Both agents run.

Expected outcomes:

- First agent receives `context["_phase_triggers"]` containing both guard outcomes before it runs.
- Second agent receives `context["_phase_triggers"]` (same) plus `context[<first_skill_id>]` (result from the first agent).
- `last-run.json` phase shows both entries with `guard.triggered: true` and `agent_result` populated.

---

## S13: Verbose status breakdown

- `last-run.json` exists with two phases, each containing at least one triggered and one skipped entry.
- `beckett status --verbose --role-target <role>`.

Expected outcomes:

- Output contains `ROLE: <name>`, `Last run:`, `Triggered:`, `Success:`, `Committed:`.
- Triggered entries show `▶ … TRIGGER … <detail>` and formatted agent result fields.
- Skipped entries show `· … SKIP   … <detail>`.
- Registry-skipped entries show `SKIP(X)`.
- `beckett status` without `--verbose` still shows the compact tabular format.
- `beckett status -v` is equivalent to `--verbose`.

---

## S14: BECKETT_LLM_CMD override

- `BECKETT_LLM_CMD=/path/to/custom-llm.sh` is set.
- Observer marker triggers `beckett-observe`.
- `invoke_claude` invokes the custom command (not plain `claude`).
- The Pirandello prompt stack is assembled and passed on stdin to the custom command.
- The custom command receives `MASKS_ROLE` in its environment.

---

## S15: BECKETT_LLM_DEBUG logs stderr

- `BECKETT_LLM_DEBUG=1` is set.
- `BECKETT_LLM_CMD` points to a script that writes `STDERR_SIGNAL` to stderr and `OK` to stdout.
- `beckett loop --skill beckett-observe --role-target <role> --force` runs with DEBUG logging enabled.
- `STDERR_SIGNAL` appears in the `beckett.loop.claude` logger at `DEBUG` level.

---

## S16: Missing guard — lenient skip

- `loop.yaml` contains an entry with `id: no-such-guard` referencing a guard not in the registry.
- `beckett loop --once --role-target <role>` runs.

Expected outcomes:

- Warning logged: `loop entry 'no-such-guard' skipped — not in registry`.
- Cycle completes with exit code `0`.
- `last-run.json` shows the entry with `skipped: true` and `guard.triggered: false`.
- `success: true` (skips are not failures).

---

## S17: Guard timeout

- `BECKETT_GUARD_TIMEOUT=1` is set (1 second).
- A guard's subprocess call sleeps for 10 seconds.
- The guard subprocess times out.

Expected outcomes:

- Timeout is handled gracefully (exception caught).
- Guard returns `triggered: false` with `detail` indicating the timeout.
- Cycle continues to remaining entries.
- `last-run.json` still written; `success: true` (timeouts are not fatal).

---

## S18: PhaseState interval cooldown

- Role has `loop.yaml` with `beckett-orient-email` entry.
- First cycle: inbox-guard passes; 15m interval has elapsed since `PhaseState.last_orient_email`; guard triggers; agent runs; `PhaseState.last_orient_email` is written to `.beckett-state/phase-state.json`.
- Second cycle immediately after: 15m has **not** elapsed.

Expected outcomes:

- Guard returns `triggered: false`; agent does not run.
- `last-run.json` shows the entry as skipped with detail indicating cooldown (interval not elapsed).

---

## S19: invoke_claude_agent uses cwd=role_dir and --plugin-dir

- `BECKETT_LLM_CMD` is set to a sentinel script.
- `beckett loop --skill beckett-orient-decisions --role-target work --force` runs.

Expected outcomes:

- `invoke_claude_agent` subprocess is called with `cwd=<work_role_dir>` and argv contains `--plugin-dir <path_to_installed_beckett/_data>` and `--agent beckett-orient-decisions` (subject to agent naming normalization in implementation).
- The sentinel script confirms `cwd` and argv via env inspection or captured args.

---

## S20: Dry-run shows all 15 beckett-* phases

- Role has valid `loop.yaml` with all 15 `beckett-*` phase entries registered.
- `beckett loop --dry-run --role-target <role>` runs.

Expected outcomes:

- Exit code `0`.
- Output lists all **15** phase entries.
- No entry shows `SKIP(X) skipped:missing-registry`.
- Each entry shows either `▶ TRIGGER` or `· SKIP` (per guard outcome) with a detail string.

---

## S21: No install step needed for agent resolution

- `beckett install --role-target <role>` runs.

Expected outcomes:

- `loop.yaml` and `.env` are provisioned under the role workspace.
- **No** Beckett-owned agent or skill files are copied into `~/.claude/agents/` or `~/.claude/skills/`.
- A subsequent `invoke_claude_agent` call with `--plugin-dir` pointing at the installed package's `beckett/_data` directory resolves the `beckett-observe` (or analogous) bundled agent definitions successfully.

---

## Test Coverage Matrix

| Scenario | pytest file | Test function |
|---|---|---|
| S1 Valid one-shot | `test_functional_loop.py` | `test_smoke_once` |
| S2 OODA-only fails | `test_doctor.py` | `test_doctor_fails_ooda_only_role` |
| S3 Multi-role continue | `test_loop_runner.py` | (runner integration) |
| S4 Partial agent failure | `test_loop_runner.py` | (error propagation) |
| S5 No changes no commit | `test_functional_loop.py` | (no marker → no commit) |
| S6 Memory write-local | `test_loop_memory.py` | (MemoryWriteError path traversal) |
| S7 Personal synthesis write | `test_loop_memory.py` | (allow_personal_synthesis) |
| S8 Status tabular | `test_status_cmd.py` | `test_status_reads_last_run_json`, `test_status_shows_never_when_missing` |
| S9 Dry-run no agents | `test_dryrun.py` | `test_dryrun_trigger_on_marker`, `test_dryrun_does_not_invoke_llm`, `test_dryrun_does_not_write_last_run`, `test_dryrun_cli_output_format` |
| S10 Per-skill --force | `test_skill_cmd.py` | `test_single_skill_force_runs_agent`, `test_skill_cli_force_output` |
| S11 OpenShell wraps subprocess | (doctor check) | `test_doctor.py` (openshell warn path) |
| S12 Two-pass trigger context | `test_functional_loop.py` | `test_two_pass_trigger_context` |
| S13 Verbose status | `test_verbose_status.py` | `test_status_verbose_cli_flag`, `test_verbose_shows_role_and_summary`, `test_verbose_triggered_skill_shows_arrow` |
| S14 LLM CMD override | `test_functional_loop.py` | `test_llm_cmd_override` |
| S15 LLM DEBUG stderr | `test_functional_loop.py` | `test_debug_mode_logs_stderr` |
| S16 Missing guard lenient | `test_functional_loop.py`, `test_dryrun.py` | `test_missing_guard_lenient`, `test_dryrun_missing_guard_skipped` |
| S17 Guard timeout | `test_functional_loop.py` | `test_guard_timeout_env` |
| S18 PhaseState interval cooldown | (TBD — phase-state persistence) | (TBD) |
| S19 invoke_claude_agent cwd + plugin-dir | (TBD — agent subprocess contract) | (TBD) |
| S20 Dry-run fifteen phases | `test_dryrun.py` (extended) | (TBD) |
| S21 install without ~/.claude copy | `test_install.py` / integration | (TBD) |
| Live: full cycle | `test_live.py` | `test_live_full_cycle` (requires `BECKETT_MODEL`) |
| Live: per-skill schemas | `test_live.py` | `test_live_observe_agent_returns_valid_schema` et al. |
