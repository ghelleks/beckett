# SDD Spec: `beckett-scheduled` Skills Aggregate

**Context:** Periodic maintenance / reporting tasks executed on **cadence composites** (**weekday/friday/global interval**) without intra-guard **hour-of-day** restrictions — aligning with **`docs/specs/beckett-loop/SPEC.md`** guard policy (use top-level **`active_hours`** if time-of-day gating needed).

Implementations SHOULD partition into discrete registry entries but share typing patterns.

---

## Shared Output Model

All four scheduled variants emit **`ScheduledResult(completed: bool)`** aggregated or explicit per-variant boolean semantics documented locally.

---

## Sub-Skill A — `beckett-scheduled-staff-update-draft`

**Implementation hint:** `cli/beckett/loop/skills/scheduled_staff_update.py` (illusory path per actual repo layout).

### Architecture

- **Guard:** **`weekday-friday`** (`datetime` `.weekday()==4`) **without hour-of-day micro gate** requirement **AND `≥7d`** elapsed since `PhaseState.last_scheduled_staff_update`.
- **Agent:** **`invoke_claude_agent`** referencing bundled staff-update agent definition.

### PhaseState

Updates **`last_scheduled_staff_update`** on success acknowledgement.

---

## Sub-Skill B — `beckett-scheduled-efficiency-log`

### Architecture

- **Guard:** **Weekday (`Mon–Fri`)** ignoring clock hour intra-guard **AND `≥24h`** since **`last_scheduled_efficiency_log`**.
- **Agent:** **Shell subprocess** appends deterministic efficiency metrics line / structured JSONL (implementation enumerated).

### PhaseState

**`last_scheduled_efficiency_log`** timestamp bumped post-successful append.

---

## Sub-Skill C — `beckett-scheduled-efficiency-email`

### Architecture

- **Guard:** Weekday (`Mon–Fri`) AND **≥24h** cooldown since `last_scheduled_efficiency_email`, plus a deterministic check that today's efficiency log artifact exists (**efficiency log written today**).
- **Agent:** **Shell** (`sendmail`-like shim or **`gws gmail send`** pipeline) attaches / references prior log path.

### PhaseState

**`last_scheduled_efficiency_email`** bumped after SMTP accept / API 200 sentinel.

---

## Sub-Skill D — `beckett-scheduled-desktop-archive`

### Architecture

- **Guard:** **`≥24h`** since **`last_scheduled_desktop_archive`** (**no weekday filter** unless future extension flagged).
- **Agent:** **`invoke_claude_agent`** executing desktop archiving skill (**kebab beckett slug** enumerated in plugin manifest).

### PhaseState

**`last_scheduled_desktop_archive`** updated afterward.

---

## Requirements (Cross-Cutting)

### Hard constraints

1. **No HH:MM gating baked inside these guards.** Day-of-week + interval conditions only (plus explicit log-exists predicate where listed).
2. **Shell subprocesses inherit role env** merges (`deps.env`).
3. **Failure semantics:** nonzero exit ⇒ runner partial failure propagation consistent with SPEC exit code **2** policy classification.
4. **Parallelism forbidden** across mutually exclusive variants accidentally double-touching mailbox — sequencing via phase ordering authoritative.
5. **Idempotency where applicable:** Efficiency email must not blindly duplicate sends if rerun inside cooldown miss window — guarded by **`≥24h` timestamp** invariant.

---

## Proposal format additions

Provide per-variant log path constants + mail recipient env keys.

---

## Static evaluation metrics (aggregate)

| ID | Name | Pass condition |
|---|---|---|
| M-SCH1 | Friday staff guard | Boundary Friday local TZ |
| M-SCH2 | Weekday vs weekend skip | Efficiency variants skip weekends |
| M-SCH3 | 24h / 7d intervals | Freeze-time tests |
| M-SCH4 | Log precondition email | Efficiency email blocked if today's log absent |
| M-SCH5 | ScheduledResult schema validity | Parsed consistently |
| M-SCH6 | No intra-guard hourly branch | AST / policy scan absent hour selectors |
