# SDD Spec: `beckett-observe` Skill

**Context:** See `docs/design.md` for full system design and `docs/specs/beckett-loop/SPEC.md` for orchestration. `beckett-observe` is the primary **observe-phase** ingest: pulls structured signals from Todoist, WorkBoard KR health, and multi-account Gmail, then writes Markdown observations under `role_dir/Memory/` using deterministic dedupe so successive loop cycles do not spam identical entries.

**Implementation:** `cli/beckett/loop/skills/observe.py`.

**Architecture:**

- **Guard (`beckett_observe_guard` / registry `beckett-observe`):** Pure Python (+ configured `@tool` reads as implementation allows). Computes `GuardOutcome`. Triggers when **any** holds: unread mail signal; marker file `.beckett-pending/observer.txt` exists; **90 minutes** elapsed since `PhaseState.last_observe`.
- **Agent (`beckett_observe_agent` / registry `beckett-observe`):** **`pydantic_ai.Agent`** (Tier 2 tools + model). Fetches overdue Todoist tasks, WorkBoard KR health signals, Gmail across configured accounts; uses `should_write_observation` dedupe before committing memory writes.
- **Output model:** `ObserveResult(signals_found: int, files_written: int, sources: list[str])`.

**Deliverables:** Guard + agent registered in loop registry; parity with Beckett Naming Convention (`beckett-` IDs, `.beckett-pending/` paths).

---

## Requirements

### Hard constraints

1. **Guard uses interval-only semantics** aligned with **`docs/specs/beckett-loop/SPEC.md` § Guard Contract** — cooldown from `PhaseState.last_observe` (no hour-of-day checks inside guard; daemon `active_hours` handles working-hour gating globally).
2. **Marker path:** `.beckett-pending/observer.txt` under `deps.role_dir` triggers regardless of unread mail (presence sufficient).
3. **Memory writes** must pass `write_memory` / `should_write_observation`: identical or near-duplicate content must not produce new observation files inside the freshness window enforced by dedupe helpers.
4. **Multi-account Gmail** reads must honor per-role `gws`/profile configuration (env + role `.env`); never cross-write memory between roles.
5. **`PhaseState.last_observe`** MUST be bumped when the skill completes successfully **after guard trigger** — persisted by runner to `.beckett-state/phase-state.json`.
6. **No git operations** inside skill module — commits happen in `runner.commit_role_changes`.

### Soft constraints

- Completes within a few minutes for typical volumes (hundreds of tasks / dozens of KR rows).
- Logged `sources` list should cite which connectors contributed (opaque labels acceptable).

---

## Proposal format

### 1. Overview

Pipeline placement: observe phase Pass 1 (guard) → Pass 2 (agent) → memory writes → INDEX maintenance via shared memory helpers.

### 2. Guard function

Pure predicate over `deps` + `deps.phase_state` + filesystem marker + deterministic inbox signal checks.

### 3. Connector tools

Enumerate `@tool`s for Todoist backlog, WorkBoard KR health summaries, Gmail triage / unread predicates.

### 4. Observation write path

Explain `should_write_observation`, target subpaths (`Memory/` tree), forbidden paths.

### 5. Runner integration

Successful run updates `ObserveResult`; runner persists PhaseState timestamps.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-O1 | Marker trigger | With `.beckett-pending/observer.txt` present, guard triggers even absent mail unread |
| M-O2 | 90m cooldown | When marker absent and unread absent, guard triggers iff ≥90m since `last_observe` |
| M-O3 | Dedupe | Duplicate observation body does not spawn second file inside dedupe window |
| M-O4 | Output schema | Successful run returns validated `ObserveResult` |
| M-O5 | No guard hour gate | Guard never branches on clock hour independent of PhaseState thresholds |
