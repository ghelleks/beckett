# SDD Scenarios: `ooda-orient-synthesis` Skill

**Companion spec:** `docs/specs/ooda-orient-synthesis/SPEC.md`  
**Date:** 2026-04-23

---

## Use Cases

### 1. Normal weekly synthesis — qualifying patterns found and written

It is Sunday. The guard script checks the day and the synthesis log — today is the configured synthesis day and synthesis has not run this week. The LLM is invoked. Across `work/Memory/` and `personal/Memory/`, the skill finds two cross-role patterns: one appearing in five work sessions and two personal sessions, and one appearing in three work sessions and one personal session. Neither pattern currently has a file in `personal/Memory/Synthesis/`.

Questions the proposal must answer:
- Does the skill write two new files to `personal/Memory/Synthesis/`, one per pattern?
- Does each file contain the required fields: pattern name, First/Last observed dates, `## Pattern` paragraph, `## Evidence` list?
- Does the Evidence list cite specific Role names and session dates for each occurrence?
- Does `personal/Memory/INDEX.md` gain two new rows for the synthesis files?
- Does `personal/.synthesis.log` gain one new entry with the timestamp and "2 patterns found, 0 updated"?

Metric cross-references: M-04, M-05, M-06, M-07, M-09, M-10, M-11

---

### 2. Guard exits — not the synthesis day

`masks run personal` fires at 9:15am on a Tuesday. The guard script checks the day: Tuesday is not Sunday (the configured `SYNTHESIS_DAY`). The guard exits non-zero. `masks run` logs `OODA_OK` and exits without invoking any LLM.

Questions the proposal must answer:
- Does the guard exit non-zero on Tuesday without running any Memory scan?
- Is `personal/.synthesis.log` unchanged — no entry written for this non-synthesis run?
- Does `masks run` handle this as a standard all-fail condition (logging OODA_OK) rather than as an error?

Metric cross-references: M-02, M-03, M-10

---

### 3. Guard exits — synthesis already ran this week

It is Sunday. The guard checks the synthesis log and finds an entry from four days ago (last Wednesday, when the synthesis day was temporarily changed). The guard exits non-zero: synthesis has run within 7 days.

Questions the proposal must answer:
- Does the guard read `personal/.synthesis.log` and correctly identify the recent entry as within the 7-day window?
- Does it exit non-zero without invoking any LLM?
- Is this a clean exit, not an error — the system is healthy, just nothing to do?

Metric cross-references: M-03

---

### 4. Pattern observed in only one Role — cross-role filter applied

The skill scans all Roles' Memory files and finds a strong pattern: the user consistently writes a one-paragraph executive summary before any longer document. This appears six times across work sessions — but never in any personal session or any other Role. It does not meet the ≥2 Roles threshold.

Questions the proposal must answer:
- Does the skill correctly classify this as a role-specific pattern rather than a cross-role one?
- Is no file written to `personal/Memory/Synthesis/` for this pattern?
- Does the run summary note the role-specific pattern as a ROLE.md candidate — making it visible without promoting it to SELF.md territory?
- Does `personal/Memory/INDEX.md` remain unchanged for this pattern?

Metric cross-references: M-05, M-06

---

### 5. Synthesis updates an existing pattern file — new evidence accumulated

Three months ago, synthesis wrote `personal/Memory/Synthesis/restructures-proposals.md` documenting a cross-role pattern with six evidence entries. Since then, four more sessions in two Roles have shown the same behavior. The current synthesis run finds all ten evidence points.

Questions the proposal must answer:
- Does the skill identify the existing `restructures-proposals.md` file and update it rather than creating a duplicate?
- Does the `## Evidence` list now contain ten entries?
- Is `**Last observed:**` updated to the most recent session date?
- Does `personal/.synthesis.log` record "0 patterns found, 1 updated" (or equivalent) to distinguish new patterns from updates?

Metric cross-references: M-07, M-08, M-10

---

### 6. A new Role was added since the last synthesis run

A user added a `consulting/` Role two months ago and has been using it actively. The previous synthesis run pre-dates this Role. This week's synthesis should now include `consulting/Memory/` in its scan.

Questions the proposal must answer:
- Does the skill discover `consulting/` as a Role directory under `$BASE` and include its Memory files in the scan?
- Does a pattern appearing in `work/` and `consulting/` (two Roles) meet the ≥2 Roles threshold even if it has never appeared in `personal/`?
- Does the proposal define how Role directories are discovered — by directory enumeration, by reading a config, or another mechanism?

Metric cross-references: M-04, M-05

---

### 7. A synthesis pattern becomes stale — no new evidence in 90 days

`personal/Memory/Synthesis/early-riser-preference.md` was written 11 months ago. The most recent evidence entry is 95 days old. The current synthesis run finds no new evidence for this pattern in any Role's Memory files.

Questions the proposal must answer:
- Does the skill mark the file with `**Status:** stale` rather than deleting it?
- Does the run summary note the stale pattern explicitly?
- Is the file otherwise left intact — evidence history preserved, dates unchanged?
- Does the `masks reflect` skill know to treat stale patterns differently (e.g., not proposing them for addition to SELF.md)? Or is staleness purely informational at this layer?

Metric cross-references: M-12

---

### 8. Skill invoked directly — not from OODA loop

A user types "run synthesis" in a `personal/` session. The guard is not in play (direct invocation bypasses the guard). The skill runs immediately.

Questions the proposal must answer:
- Does the skill verify it is running from the `personal/` workspace root and proceed normally?
- Does it present a summary of what it found before writing — giving the user visibility before files are committed?
- Does it still write to `personal/Memory/Synthesis/` and update the log, producing the same output as an OODA-triggered run?
- If the user invokes it from a `work/` session, does it warn and exit rather than writing to the wrong location?

Metric cross-references: M-01, M-07, M-09, M-10, M-11

---

## Stress Tests

**T1 Guard exits non-zero on any day that is not the configured synthesis day.**  
On every day of the week except the configured `SYNTHESIS_DAY`, the guard script exits non-zero without performing any Memory scan or writing any log entry.  
Pass: running the guard script six days out of seven produces no LLM invocation, no synthesis file changes, and no synthesis log entries.

**T2 All Role directories under `$BASE` are scanned.**  
Every Role directory that exists under `$BASE` at run time has its `Memory/` directory read — including Roles added after the last synthesis run.  
Pass: a system with four Role directories produces synthesis that has read from all four; a system where only three of four are scanned fails this test.

**T3 No pattern is written with fewer than 3 sessions or fewer than 2 Roles of evidence.**  
Every file in `personal/Memory/Synthesis/` that the skill created or updated in a given run cites ≥3 distinct session dates OR ≥2 distinct Role names in its `## Evidence` section.  
Pass: inspection of any synthesis file finds its evidence list meets the threshold; files with one Role and two sessions fail.

**T4 No role-specific pattern is written to `personal/Memory/Synthesis/`.**  
A pattern appearing only in `work/Memory/` — regardless of how many work sessions it appears in — is not written to `personal/Memory/Synthesis/`.  
Pass: after a synthesis run where the strongest pattern appears exclusively in the work Role, `personal/Memory/Synthesis/` contains no file for that pattern.

**T5 Existing synthesis files are updated in place, not duplicated.**  
When a pattern file already exists in `personal/Memory/Synthesis/`, running synthesis again with new evidence updates the file rather than creating a second file.  
Pass: `personal/Memory/Synthesis/` contains exactly one file per pattern; `git log` on any synthesis file shows a single continuous history with update commits, not parallel files.

**T6 `personal/Memory/INDEX.md` reflects all synthesis file changes.**  
After a run that creates two new synthesis files and updates one existing file, `INDEX.md` has two new rows and one updated row.  
Pass: every file in `personal/Memory/Synthesis/` has a corresponding row in `INDEX.md`; no synthesis file is absent from the index.

**T7 `personal/.synthesis.log` gains exactly one entry per run.**  
Each invocation of the synthesis skill (whether it finds patterns or not) appends exactly one line to `personal/.synthesis.log`.  
Pass: after three weekly runs, the log has three entries; a run that writes no log entry fails this test.

**T8 Skill writes no git operations.**  
The skill source contains no `git add`, `git commit`, `git push`, or branch operation calls. The session-end hook handles committing synthesis file changes.  
Pass: `grep -r "git commit\|git push\|git add" skills/ooda-orient-synthesis/` returns no results.

**T9 Stale patterns are marked, not deleted.**  
A synthesis file whose most recent evidence entry is more than 90 days old is updated to include `**Status:** stale` — the file and its evidence history are otherwise preserved.  
Pass: after a synthesis run, stale files are present in `personal/Memory/Synthesis/` with the stale marker; no synthesis file is deleted by the skill.

**T10 Direct invocation from wrong workspace root exits with a warning.**  
If the skill is invoked from a non-personal workspace root (e.g., from `work/`), it logs a warning and exits without reading any Memory files or writing any synthesis files.  
Pass: invoking the skill from `~/Desktop/work/` produces a warning and zero file changes; `personal/Memory/Synthesis/` is unchanged.

---

## Anti-Pattern Regression Signals

**Role-specific patterns written to `personal/Memory/Synthesis/`.** The skill writes a pattern observed only in the work Role to `personal/Memory/Synthesis/`. Symptom: `masks reflect` proposes work-specific behaviors for SELF.md; after a job change, SELF.md contains obsolete work-context claims. Indicates: cross-role filter (M-06) not implemented; all patterns above the session threshold are written regardless of Role distribution. Maps to: M-06.

**Evidence threshold not enforced.** The skill writes a synthesis file for a pattern observed in only one session of one Role. Symptom: `personal/Memory/Synthesis/` fills with one-off observations; `masks reflect` has low-quality evidence for all proposed SELF.md changes; the reflect PR history oscillates rather than converges. Indicates: threshold check not implemented or bypassed. Maps to: M-05.

**Synthesis file duplicated on update.** Each synthesis run creates a new file for the same pattern rather than updating the existing one. Symptom: `personal/Memory/Synthesis/` accumulates files like `restructures-proposals-2026-01.md`, `restructures-proposals-2026-04.md`; INDEX.md grows redundantly; `delete_by_tag` on the old file leaves orphaned database entries. Indicates: existing file not found before write; M-08 not implemented. Maps to: M-08.

**`personal/.synthesis.log` not written.** Synthesis runs complete without writing to the log. Symptom: the guard's already-ran check always fails to find a recent entry; synthesis runs every day instead of once a week; Memory files are re-scanned and re-written unnecessarily. Indicates: log write step missing or conditional on finding patterns. Maps to: M-10.

**Synthesis writes to wrong Role's Memory.** When invoked from a work session, the skill writes to `work/Memory/Synthesis/` instead of `personal/Memory/Synthesis/`. Symptom: synthesis observations land in the work git repo (company custody) rather than the personal repo; cross-role patterns about the person become employer property; `masks reflect` cannot find them. Indicates: M-01 workspace root check not implemented. Maps to: M-01.
