# SDD Spec: `beckett-observe-context-refresh` Skill

**Context:** Periodically validates **CONTEXT.md** fidelity against episodic observations in **`Memory/`** using full agentic MCP tool access (`invoke_claude_agent`). Addresses staleness exceeding what pure-Python heuristics can safely rewrite.

**Implementation:** `cli/beckett/loop/skills/observe_context_refresh.py` (path per impl).

**Architecture:**

- **Guard:** **`≥72h`** since `PhaseState.last_observe_context_refresh` (**interval-only**).
- **Agent:** **`invoke_claude_agent("beckett-observe-context-refresh", …)`** with `cwd = deps.role_dir`, `--plugin-dir` bundle path, **`--max-budget-usd`** from `BECKETT_AGENT_BUDGET_USD`. Agent reviews Memory markdown for outdated claims; emits structured JSON aligning with **`ContextRefreshResult`**.
- **Output model:** `ContextRefreshResult(files_reviewed: int, updated: int)`.

---

## Requirements

### Hard constraints

1. **Frequency:** Guard checks **elapsed hours only** vs PhaseState (**72h**) — never business-hour-of-day branching.
2. **Invocation contract:** Exact CLI tier-3 invocation per **`docs/specs/beckett-loop/SPEC.md` § Tier 3**.
3. Writes limited to sanctioned files (`CONTEXT.md`, optional appendix note files under role root if policy expands — MUST be enumerated in implementation checklist).
4. **JSON parse resilience:** Malformed Claude output ⇒ skill failure surfaced; partial updates forbidden without explicit transaction semantics documented.
5. PhaseState **`last_observe_context_refresh`** update on acknowledged success **only**.
6. **No silent cross-role reads** beyond permitted Memory scope for current role unless policy ratified globally (default: forbid).

### Soft constraints

- Dry-run skips agent (`beckett loop --dry-run`) — SPEC global rule.

---

## Proposal format

### 1. Overview

Bridge between unstructured Memory growth and CONTEXT narrative coherence.

### 2. MCP expectations

Enumerate expected tool families (filesystem read, selective doc patch).

### 3. Failure taxonomy

Budget exceeded vs parse error vs user cancellation.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-CR1 | 72h interval | Boundary exactness tests |
| M-CR2 | invoke_contract | Stub sees `--agent beckett-observe-context-refresh` + plugin dir |
| M-CR3 | cwd role | cwd equals `deps.role_dir` |
| M-CR4 | Result schema | JSON maps to ContextRefreshResult |
| M-CR5 | State bump | Only after success |
