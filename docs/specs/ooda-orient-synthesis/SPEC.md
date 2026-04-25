# SDD Spec: `ooda-orient-synthesis` Skill

**Context:** See `docs/design.md` for full system design. This spec covers the weekly cross-Role synthesis pass — the one agent that deliberately exercises the global-read rule by reading Memory/ files across all Roles, identifying cross-role patterns, and writing synthesis observations to `personal/Memory/Synthesis/`. Its output is the raw material that `masks reflect` reads when building SELF.md proposals.

**Deliverables:** `skills/ooda-orient-synthesis/SKILL.md`, `guards/ooda-orient-synthesis.sh`. Listed as an Agenda item in `personal/OODA.md` only — not in any work or other Role's OODA.

---

## Requirements

### Hard constraints

1. **Must run from `personal/` workspace root.** The skill reads across all Roles' `Memory/` directories and writes to `personal/Memory/Synthesis/`. Running from any other workspace root is an error — the skill must log a warning and exit without performing any reads or writes.
2. The **guard script** (`guards/ooda-orient-synthesis.sh`) enforces two conditions before the LLM is invoked:
   - Today is the configured synthesis day (default: Sunday). Configurable via `SYNTHESIS_DAY` in `$BASE/.env` (0=Sunday … 6=Saturday).
   - Synthesis has not already run this week: no entry in `$BASE/personal/.synthesis.log` dated within the past 7 days.
   - If either condition fails, the guard exits non-zero. `masks run` logs `OODA_OK` and no LLM is started.
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

- When invoked from the OODA loop: runs silently, no user interaction required.
- When invoked directly from a session: may present a summary of patterns found before writing, giving the user visibility into what will be committed.
- The skill should complete in under 60 seconds for a system with ≤500 total Memory files across all Roles.

---

## Proposal format

### 1. Overview
How the skill sits in the pipeline: guard → synthesis → masks reflect → PR. What "cross-role pattern" means operationally and how it differs from a role-specific observation.

### 2. Guard script
The exact guard logic for `guards/ooda-orient-synthesis.sh`: day-of-week check, already-ran-this-week check, how `SYNTHESIS_DAY` is read from the environment.

### 3. Memory scan
Which directories are scanned and in what order. How the skill determines which Role directories exist under `$BASE`. How session dates are inferred from Memory file content or git history.

### 4. Pattern detection
The algorithm for clustering observations into patterns. How the ≥3-session / ≥2-Role threshold is applied. How the skill distinguishes cross-role patterns from role-specific ones.

### 5. Synthesis file writes
The exact format of each `personal/Memory/Synthesis/<name>.md` file. How existing files are identified and updated vs. new files created. How naming conflicts are handled.

### 6. Stale pattern handling
The 90-day staleness rule. How the skill marks stale patterns and what it writes to the run summary about them.

### 7. Log format
The exact line format written to `personal/.synthesis.log`. What "N patterns found, M updated" means operationally.

### 8. Self-check table
See Static Evaluation Metrics.

---

## Static evaluation metrics

| ID   | Name                  | Pass condition                                                                                              |
|------|-----------------------|-------------------------------------------------------------------------------------------------------------|
| M-01 | Personal root only    | Skill logs a warning and exits without reading or writing if `$PWD` is not the `personal/` Role directory   |
| M-02 | Day-of-week guard     | Guard exits non-zero on any day other than the configured `SYNTHESIS_DAY`; no LLM is invoked               |
| M-03 | Already-ran guard     | Guard exits non-zero if `personal/.synthesis.log` contains an entry dated within the past 7 days            |
| M-04 | All Roles scanned     | Memory/ is read from every Role directory under `$BASE`; no Role is skipped                                 |
| M-05 | Evidence threshold    | No pattern file is written with fewer than 3 sessions or fewer than 2 Roles of evidence                    |
| M-06 | Cross-role filter     | No pattern observed only in a single Role is written to `personal/Memory/Synthesis/`                        |
| M-07 | Synthesis file format | Every written file contains: pattern name heading, First/Last observed dates, `## Pattern`, `## Evidence`   |
| M-08 | In-place update       | Re-running synthesis on an existing pattern updates the file rather than creating a duplicate               |
| M-09 | INDEX.md updated      | `personal/Memory/INDEX.md` reflects any new or modified synthesis files after each run                     |
| M-10 | Log written           | `personal/.synthesis.log` gains one new line on every completed run, with timestamp and pattern counts      |
| M-11 | No git operations     | Skill does not call `git add`, `git commit`, `git push`, or any branch operation                            |
| M-12 | Stale marked          | Patterns with no evidence in the past 90 days are marked `Status: stale` in their file, not deleted        |
