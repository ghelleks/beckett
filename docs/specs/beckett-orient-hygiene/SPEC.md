# SDD Spec: `beckett-orient-hygiene` Skill

**Context:** Reviews Gmail threads labeled **`reply_needed`** ensuring stale / duplicate / superseded drafts are consolidated or delegated.

**Implementation:** `cli/beckett/loop/skills/orient_hygiene.py`.

**Architecture:**

- **Guard:** **`≥20m`** since `PhaseState.last_orient_hygiene` AND **label predicate** satisfied: deterministic query proves **`reply_needed` label has ≥1 message** (pure Python/`gws` query wrapper).
- **Agent:** **`invoke_claude_agent("beckett-orient-hygiene", …)`**.
- **Output model:** **`HygieneResult(threads_reviewed: int, actions_taken: int)`** (archive, label churn, escalation tasks — enumerated in implementation appendix).

---

## Requirements

### Hard constraints

1. **Interval-only cooldown** (**20m**); no intra-guard weekday/HH-MM windows.
2. **Label predicate** must be deterministic (no LLM).
3. **Thread scope limit** policy protects token budget (implicit max threads default documented).
4. PhaseState **`last_orient_hygiene`** bumped only successful completion aggregate.
5. **Side effects reversible where possible**: archive vs delete semantics enumerated.

### Soft constraints

- Idempotent labeling: rerunning hygiene should converge labels (no oscillation ladder).

---

## Proposal format

### 1. Overview

Feeds downstream `beckett-orient-reply-drafter` quality by normalizing backlog edges.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-OH1 | Label gate correctness | Fixtures with synthetic label counts |
| M-OH2 | Interval | 20m boundary |
| M-OH3 | invoke contract | agent name correctness |
| M-OH4 | Schema validity | HygieneResult |
| M-OH5 | No hour gate inside guard |
