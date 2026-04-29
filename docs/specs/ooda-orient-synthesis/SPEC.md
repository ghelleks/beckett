# SDD Spec: `ooda-orient-synthesis` Skill

**Context:** See `docs/design.md` for full system design. This spec covers the weekly cross-Role synthesis pass — the one agent that deliberately exercises the global-read rule by reading Memory/ files across all Roles, identifying cross-role patterns, and writing synthesis observations to `personal/Memory/Synthesis/`. Its output is the raw material that `masks reflect` reads when building SELF.md proposals.

**Implementation:** `cli/beckett/loop/skills/orient_synthesis.py`. Listed as a `mask-ooda-orient-synthesis` entry in the personal role `LoopSpec`.

**Architecture:** The skill uses the Beckett three-tier agent model:
- **Guard (`orient_synthesis_guard`):** Pure Python predicate — `GuardFn` returning `GuardOutcome`. Checks day-of-week and cooldown log. No subprocess calls.
- **Agent (`orient_synthesis_agent`):** `pydantic_ai.Agent` with `@tool` functions for memory reads and writes. The LLM reasons over tool outputs to identify patterns and draft synthesis entries. Rule 7 housekeeping (`.synthesis.log` update) happens in the Python agent function after `agent.run()` returns, not inside the LLM call.
- **Output model:** `SynthesisResult(patterns_found: int, written: int, stale_updated: int)`.

**Deliverables:** Loop runtime guard/agent implementation in `cli/beckett/loop/skills/orient_synthesis.py`. The agent-skills `mask-ooda-orient-synthesis/SKILL.md` remains the independently-invocable Claude Code skill; Beckett does not reimplement it (per Rule 6).

---

## Requirements

### Hard constraints

1. **Must run from `personal/` workspace root.** The skill reads across all Roles' `Memory/` directories and writes to `personal/Memory/Synthesis/`. Running from any other workspace root is an error — the skill must log a warning and exit without performing any reads or writes.
2. The **guard function** (`mask-ooda-orient-synthesis`) enforces two conditions before the agent is invoked:
   - Today is the configured synthesis day (default: Sunday). Configurable via `SYNTHESIS_DAY` in `$BASE/.env` (0=Sunday … 6=Saturday).
   - Synthesis has not already run this week: no entry in `$BASE/personal/.synthesis.log` dated within the past 7 days.
   - If either condition fails, the guard returns `triggered=false` and no synthesis agent is started.
3. **Reads Memory/ from every Role** under `$BASE`. It must not skip any Role directory, including newly added Roles not previously seen by synthesis.
4. **Evidence threshold:** a pattern is valid for synthesis output only if it appears in ≥3 distinct sessions OR ≥2 distinct Roles. Evidence is citeable: specific session dates (from Memory file timestamps or content) and Role names.
5. **Cross-role filter:** patterns specific to a single Role are not written to `personal/Memory/Synthesis/`. A pattern that appears six times in `work/` but never in any other Role is a ROLE.md candidate, not a SELF.md candidate. The skill may note role-specific patterns in its run summary but must not write them to `personal/Memory/`.
6. **Synthesis observation format:** each qualifying pattern is written as a separate markdown file to `personal/Memory/Synthesis/<kebab-pattern-name>.md` containing exactly:
   - `# [Pattern name]`
   - `**First observed:** YYYY-MM-DD`
   - `**Last observed:** YYYY-MM-DD`
   - `## Pattern`
   - One paragraph describing the observed behavior in cross-role terms.
   - `## Evidence`
   - A bulleted list: one entry per occurrence, formatted as `- [Role] — [session date] — [one-sentence description of the observation]`
7. **Existing synthesis files are updated in place**, not duplicated. If a pattern file already exists and new evidence has accumulated since the last synthesis, the skill updates the `## Evidence` list and the `**Last observed:**` date. It does not create a second file for the same pattern.
8. **`personal/Memory/INDEX.md` must be updated** for any new or modified synthesis files.
9. **`personal/.synthesis.log` is written** on every completed run: one line per run in the format `SYNTHESIS [ISO timestamp] — [N] patterns found, [M] updated`.
10. The skill does not commit, push, create branches, or open PRs. The session-end hook commits `personal/Memory/Synthesis/` changes. `masks reflect` reads from synthesis files on its next invocation.
11. **Stale pattern pruning:** if a synthesis file's most recent evidence is more than 90 days old and no new evidence has been found in the current run, the skill marks the pattern as `**Status:** stale` in the file and notes it in the run summary. It does not delete the file.

### Soft constraints

- When invoked from `beckett loop`: runs silently, no user interaction required.
- When invoked directly from a session: may present a summary of patterns found before writing, giving the user visibility into what will be committed.
- The skill should complete in under 60 seconds for a system with ≤500 total Memory files across all Roles.

---

## Proposal format

### 1. Overview
How the skill sits in the pipeline: guard function → synthesis agent → masks reflect → PR. What "cross-role pattern" means operationally and how it differs from a role-specific observation.

### 2. Guard function
The guard is implemented as `orient_synthesis_guard(deps: RoleDeps) -> GuardOutcome` — a pure Python async function. `SYNTHESIS_DAY` is read from `deps.env.get("SYNTHESIS_DAY", "0")` (not from `os.environ` directly, so role-local `.env` takes precedence). The already-ran check reads `deps.personal_dir / ".synthesis.log"` and parses `SYNTHESIS <ISO-timestamp>` lines; if any timestamp is within the past 7 days, the guard returns `triggered=False`. The guard never invokes any subprocess.

### 3. Memory scan
Which directories are scanned and in what order. How the skill determines which Role directories exist under `$BASE`. How session dates are inferred from Memory file content or git history.

### 4. Pattern detection
The algorithm for clustering observations into patterns. How the ≥3-session / ≥2-Role threshold is applied. How the skill distinguishes cross-role patterns from role-specific ones.

### 5. Synthesis file writes
The exact format of each `personal/Memory/Synthesis/<name>.md` file. How existing files are identified and updated vs. new files created. How naming conflicts are handled.

The agent calls `write_synthesis(subpath, content)` — a `@tool` that wraps `write_memory(deps, subpath, content, allow_personal_synthesis=True)`. The Python layer enforces: (a) `subpath` must start with `"Synthesis/"`, (b) `allow_personal_synthesis=True` is required, (c) the target must resolve within `personal/Memory/Synthesis/`. Any attempt to write outside this path raises `MemoryWriteError` and is rejected before any file is created.

### 6. Stale pattern handling
The 90-day staleness rule. How the skill marks stale patterns and what it writes to the run summary about them.

### 7. Log format
The exact line format written to `personal/.synthesis.log`. What "N patterns found, M updated" means operationally.

**Rule 7 housekeeping note:** the `.synthesis.log` write is performed by the Python `orient_synthesis_agent` function **after** `agent.run()` returns — it is not part of the LLM call. This ensures the log is always written even if the LLM produces no synthesis files, and that the log format is controlled deterministically by Python. The LLM is responsible for deciding *what* to write; Python is responsible for recording *that* the run happened.

### 8. Self-check table
See Static Evaluation Metrics.

---

## Static evaluation metrics

| ID   | Name                  | Pass condition                                                                                              |
|------|-----------------------|-------------------------------------------------------------------------------------------------------------|
| M-01 | Personal role only    | `orient_synthesis_agent` checks `deps.role == "personal"`; returns `detail: "requires personal role"` without reading or writing if running in any other role |
| M-02 | Day-of-week guard     | `orient_synthesis_guard` returns `triggered=False` on any day other than `SYNTHESIS_DAY` (read from `deps.env`); no synthesis agent is invoked |
| M-03 | Already-ran guard     | `orient_synthesis_guard` parses `deps.personal_dir / ".synthesis.log"` and returns `triggered=False` if any `SYNTHESIS <timestamp>` line is dated within the past 7 days |
| M-04 | All Roles scanned     | `list_role_memory_files` @tool enumerates Role directories via `deps.masks_base`; no Role is skipped        |
| M-05 | Evidence threshold    | No pattern file is written with fewer than 3 sessions or fewer than 2 Roles of evidence                    |
| M-06 | Cross-role filter     | No pattern observed only in a single Role is written to `personal/Memory/Synthesis/`                        |
| M-07 | Synthesis file format | Every file written by `write_synthesis` contains: pattern name heading, First/Last observed dates, `## Pattern`, `## Evidence` |
| M-08 | In-place update       | Re-running synthesis on an existing pattern calls `write_synthesis` on the existing path, updating rather than creating a duplicate |
| M-09 | INDEX.md updated      | `write_memory` (called by `write_synthesis`) creates or preserves `personal/Memory/INDEX.md` for any new or modified synthesis files |
| M-10 | Log written           | `orient_synthesis_agent` appends one `SYNTHESIS <ISO-timestamp> — N patterns found, M updated` line to `personal/.synthesis.log` after every completed `agent.run()` (Rule 7 housekeeping) |
| M-11 | No git operations     | `orient_synthesis.py` contains no `git add`, `git commit`, `git push`, or branch operation calls; git is handled by `commit_role_changes` in the runner |
| M-12 | Stale marked          | Patterns with no evidence in the past 90 days are marked `**Status:** stale` by the LLM via `write_synthesis`; files are not deleted |
