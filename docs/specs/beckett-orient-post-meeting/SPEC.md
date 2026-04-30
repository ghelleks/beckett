# SDD Spec: `beckett-orient-post-meeting` Skill

**Context:** Mines ended meetings for latent action items, producing **Todoist** tasks so commitments do not dissipate post-call.

**Implementation:** `cli/beckett/loop/skills/orient_post_meeting.py`.

**Architecture:**

- **Guard:** **`≥30m`** since `PhaseState.last_orient_post_meeting` (**interval-only**) AND **`≥1`** meeting concluded within **past `90 minutes` window**, AND **`event ID ∉ processed-set`** (`PhaseState` extension field mirroring prep dedupe semantics).
- **Agent:** **`invoke_claude_agent("beckett-orient-post-meeting", …)`** aggregates transcript retrieval + MCP Todoist inserts.
- **Output model:** **`PostMeetingResult(meetings_processed: int, tasks_created: int)`**.

---

## Requirements

### Hard constraints

1. **Window geometry:** **`ended ∈ (now−90m, now]`** (document inclusive/exclusive ends — tests lock choice).
2. **Transcript prerequisite policy:** If transcript missing, behavior must choose explicit skip vs heuristic calendar-only extraction (**declared**, not silent nop).
3. **Task idempotency:** Hash triplet `(event_uid, normalized_action_text)` forbids duplication.
4. **Processed event IDs persisted** akin to prep skill.
5. PhaseState timestamps & sets updated after acknowledged success boundary.
6. **No intra-guard weekday hour-of-day gating.**

### Soft constraints

- Summaries surfaced at INFO minimally redacted.

---

## Proposal format

### 1. Transcript linkage strategy

Enumerate calendar attachment fields / Meet artifacts mapping.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-OPM1 | Temporal window | Fixtures straddling boundary |
| M-OPM2 | Dedup | Repeated loop no duplicate Todoist creations |
| M-OPM3 | Invoke contract | agent slug matches |
| M-OPM4 | Interval | `30m` correctness |
| M-OPM5 | Schema | PostMeetingResult |
