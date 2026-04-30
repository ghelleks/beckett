# SDD Spec: `beckett-orient-todo-forwarder` Skill

**Context:** Moves **`todo`**-labeled actionable mail into Todoist ingestion pipeline by **deterministic MIME forward** rewrite — ensures privacy-sensitive routing without hallucination risk.

**Implementation:** `cli/beckett/loop/skills/orient_todo_forwarder.py`.

**Architecture:**

- **Guard:** **`≥15m`** since `PhaseState.last_orient_todo_forwarder` AND **deterministic Gmail query**: messages labeled **`todo`** AND lacking **`todo-forwarded`** sentinel label (exact label naming per policy YAML).
- **Agent:** **Pure Python** orchestration (**no LLM**):
  1. `gws get --format raw` (or equivalent RFC 2822 retrieval)
  2. Rewrite **From / To / Subject** headers preserving body + attachments semantics (policy enumerates multipart handling)
  3. **`gws send`** (or MIME inject API)
  4. **`todo-forwarded` label apply + archive** deterministic sequence
- **Output model:** **`TodoForwardResult(forwarded: int, failed: int)`**.

---

## Requirements

### Hard constraints

1. **Zero LLM** usage anywhere in module graph for this skill.
2. **Idempotency:** After **`todo-forwarded`** label applied successfully, future queries **never** enqueue same message (**primary dedupe key**: Gmail `Message-Id`).
3. **Ordering:** On partial batch failure, document whether remaining continue or transactional abort (**must be deterministic** selection).
4. **Credential scope:** Sends only via configured Todoist ingestion address from env (**no hard-coded inbox** literals in source).
5. PhaseState **`last_orient_todo_forwarder`** after overall batch completion acknowledging policy (partial success enumerated).
6. **Guard intervals only** (`15m`).

### Soft constraints

- Attachment size ceilings with explicit skip counted in `failed` with reason tokens.

---

## Proposal format

### 1. Header rewrite table

Enumerate prohibited headers stripped (Received chain etc.) vs preserved.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-OTF1 | Pure python | AST grep Claude/pydantic agent imports absent |
| M-OTF2 | Idempotent | Replay results `forwarded=0` extras |
| M-OTF3 | Label gating accuracy | Fixtures with combos |
| M-OTF4 | Interval | `15m` |
| M-OTF5 | MIME integrity | Attachment roundtrip hash fixture |
