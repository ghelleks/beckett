# SDD Spec: `beckett-orient-meeting-prep` Skill

**Context:** Prepares stakeholder briefings for imminent calendar events (**≤24h window**) using MCP-assisted research orchestration executed **per meeting**.

**Implementation:** `cli/beckett/loop/skills/orient_meeting_prep.py`.

**Architecture:**

- **Guard:** **`≥30m`** since `PhaseState.last_orient_meeting_prep` (**interval-only**) AND **`≥1`** calendar event qualifies: start time within **`now..now+24h`**, excluding events already accounted for via **processed event-ID set** stored in **`PhaseState` extension** (**dedupe** persists across loops).
- **Agent orchestration:**
  1. Query calendar provider for candidate events (**deterministic tool path**).
  2. For each qualifying remaining event invoke **`invoke_claude_agent("beckett-meeting-preparer", …)`** in **`ThreadPoolExecutor`** (parallel bounded).
- **Output model:** **`MeetingPrepResult(meetings_prepped: int)`** (aggregate success count vs scheduled — partial semantics documented).

---

## Requirements

### Hard constraints

1. **Dedup store** MUST survive subprocess boundaries — persists in `phase-state.json` alongside datetime fields (**set or list serialization spec** enumerated in implementation checklist).
2. **Parallel fan-out respects per-agent budget** aggregated vs individual — document cap strategy (max USD per invocation vs global).
3. **Calendar clock** uses **`deps`/role timezone** — no naive-local mixing silently shifting day boundaries.
4. **Skipping all-hands heuristic** optional but if present must be deterministic rule-set (explicit).
5. **No hour-of-day gating beyond global `active_hours`** within guard internals.
6. PhaseState bookkeeping updates after batch completion aligning with successes.

---

## Proposal format

### 1. Event qualification predicate

Enumerate filters (declined attendance, tentative optional skip policy).

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-OMP1 | Dedup correctness | Repeated cycle doesn't re-trigger same UID |
| M-OMP2 | Interval boundary | `30m` |
| M-OMP3 | Parallel invocation count | Mirrors eligible events modulo worker cap |
| M-OMP4 | Schema validity | MeetingPrepResult |
| M-OMP5 | Time window | Boundary inclusive/exclusive semantics tested |
