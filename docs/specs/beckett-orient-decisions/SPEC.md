# SDD Spec: `beckett-orient-decisions` Skill

**Context:** Synthesizes **Memory/** observation batch into prioritized **Todoist** actions (orientation layer). Executes only when refreshed signals exist since prior synthesis run windows.

**Implementation:** `cli/beckett/loop/skills/orient_decisions.py` (path per impl).

**Architecture:**

- **Guard:** **`≥30m`** since `PhaseState.last_orient_decisions` **AND** **≥1 new observation artifact** newer than **`last_orient_decisions` timestamp**, determined by **`Memory/`** markdown `mtime` / lexicographic filename policy (implementation must document deterministic ordering).
- **Agent:** **`invoke_claude_agent("beckett-orient-decisions", …)`** — reads pointers or full observation bodies, synthesizes actions, emits structured results.
- **Output model:** `DecisionsResult(decisions_synthesized: int, written: int)` (written = tasks/comments created deterministically surfaced).

---

## Requirements

### Hard constraints

1. **Guard predicates are interval-only** + **mtime batch detection** — no hour-of-day gating intrinsic to guard.
2. **`invoke_claude_agent` contract:** Tier 3 invocation + JSON output mapping (`--output-format json`).
3. **Todoist mutations** obey idempotency: repeated run with stale batch must not multiply identical tasks (**hash / fingerprint** recommendation).
4. PhaseState **`last_orient_decisions`** updates success-only.
5. **Failure isolation:** Incomplete JSON → surfaced error path; Todoist mutations wrapped transactionally **per decision** OR explicit compensating behavior documented.

### Soft constraints

- Summaries routed to stdout logger for diagnostics at INFO.

---

## Proposal format

### 1. Overview

Guard ensures **novelty**, agent ensures **conversion** of observations → executable tasks.

### 2. Novelty Detection Algorithm

Enumerate selection of eligible file glob, recursion depth, exclusions (`Synthesis/` special cases optional).

### 3. MCP tools

Skills inside plugin agent may call Todoist + memory readers.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-OD1 | Interval | 30m boundary correct |
| M-OD2 | Novelty | Suppress trigger if mtimes older than sentinel |
| M-OD3 | invoke path | Proper agent naming + cwd + plugin dir |
| M-OD4 | Result schema | DecisionsResult valid |
| M-OD5 | Idempotent repeat | Same Memory snapshot → duplicate tasks forbidden |
