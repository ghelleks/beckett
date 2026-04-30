# SDD Spec: `beckett-orient-reply-drafter` Skill

**Context:** Generates **draft Gmail replies** for threads still flagged **`reply_needed`** **without** composer draft artifact (explicit detection policy required).

**Implementation:** `cli/beckett/loop/skills/orient_reply_drafter.py`.

**Architecture:**

- **Guard:** **`≥15m`** since `PhaseState.last_orient_reply_drafter`
  - **`last_orient_email` must be populated** (**orient-email precondition** sentinel)
  - **≥1** `reply_needed` thread lacking draft per deterministic heuristic (**no LLM**) — inspect RFC822 metadata / Gmail draft markers as implementation chooses (**document heuristic** rigorously).
- **Agent:** **`invoke_claude_agent("beckett-orient-reply-drafter", …)`**.
- **Output model:** **`ReplyDraftResult(drafts_created: int)`**.

---

## Requirements

### Hard constraints

1. **Guards purely interval / structural** — heuristic existence checks must not invoke LLMs.
2. **Dependency:** **`last_orient_email` Truth** ensures classifications fresh — document edge case if classify skipped due to outage.
3. **Draft duplication prevention:** verifying draft presence leverages Gmail API deterministic fields.
4. PhaseState **`last_orient_reply_drafter`** after success-only.
5. **Privacy:** drafts never log full bodies at INFO unless redaction shim active.

---

## Proposal format

### 1. Draft absence detection

Enumerate algorithm (search `in:drafts` vs threading id association).

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-ORD1 | Email dependency | Blocks if PhaseState lacks email pass |
| M-ORD2 | Interval boundary | `15m` |
| M-ORD3 | Heuristic pure | Fixture threads with/without drafts |
| M-ORD4 | Output schema | ReplyDraftResult |
| M-ORD5 | MCP invocation | Proper agent slug |
