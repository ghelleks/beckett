# SDD Spec: `beckett-act` Skill

**Context:** Executes high-leverage backlog items surfaced as Todoist **`@agent`** tasks or qualifying **`@decision`** annotated tasks referencing user instruction threads / comments schema.

**Implementation:** `cli/beckett/loop/skills/act.py`.

**Architecture:**

- **Guard:** **≥1 Todoist tasks** labeled **`@agent`** **OR** **≥1 `@decision`** task meeting **instruction comment** predicate (deterministic extraction from description / comments API — enumerated in impl).
- **Agent:** **`pydantic_ai.Agent`** iterates queued tasks sequentially (unless parallel fork explicitly future-scoped — default sequential for determinism): dispatches **`invoke_claude_agent`** branches for compound actions vs direct API micro-tools (**GitHub**/Drive/Todoist) for trivial automation.
- **Completion:** Tasks marked **`complete`** respecting **Todoist recurrence** semantics (schedule next occurrence rather than prematurely closing perpetual patterns).
- **Output model:** **`ActResult(executed: int, failed: int, task_ids: list[str])`** (string IDs stable lexical format).

---

## Requirements

### Hard constraints

1. **`@agent`/`@decision` detection deterministic** via parser over structured fields (**no ML classification** gate).
2. **Side effects enumerated & auditable**: each sub-action logs correlated `task_id`.
3. **`invoke_claude_agent` delegated only** when MCP multi-step unavoidable — simple closures stay Python tools.
4. **Failure isolation:** Failure on task **T1** advances to **T2** unless transactional policy states otherwise (**document choice** explicitly).
5. **Recurring completeness:** Closing vs shifting due date aligns with Todoist recurrence API contract tests.
6. Guard **does not incorporate hour-of-day** business selectors (global daemon gate only).

### Soft constraints

- Optional priority ordering (priority field desc, due asc).

---

## Proposal format

### 1. Task iteration algorithm

Enumerate stable sort basis.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-A1 | Guard label accuracy | Fixtures with combinatory labels |
| M-A2 | Decision predicate | Commentary schema negative cases |
| M-A3 | Recurrence correctness | Completed repeat spawns successor |
| M-A4 | Delegation branching | Invocation counts per path |
| M-A5 | ActResult validity | Fields populated after mixed success |
