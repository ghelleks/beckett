# SDD Spec: `beckett-observe-rss` Skill

**Context:** Lightweight RSS ingestion path using `rss2email` (`r2e`). Poll feeds on an interval unrelated to unread-mail noise; complements `beckett-observe` without invoking an LLM.

**Implementation:** `cli/beckett/loop/skills/observe_rss.py` (path per implementation package layout).

**Architecture:**

- **Guard:** Preconditions: **r2e** configuration file **`~/.config/rss2email/config.cfg`** exists **AND** **`≥90m`** since `PhaseState.last_observe_rss` (pure Python + filesystem stat + PhaseState timestamps).
- **Agent:** **`subprocess`** / shell runner invokes `r2e run` non-interactively; parses stdout/stderr or exit code for surfaced counts (`feeds_polled`, `items_found`).
- **Output model:** `RssResult(feeds_polled: int, items_found: int)`.

**Deliverables:** Registry wiring; `.beckett-state/phase-state.json` persistence of `last_observe_rss` after successful subprocess completion.

---

## Requirements

### Hard constraints

1. **Never run** if config path missing → guard skips with explicit detail.
2. **Interval-only cooldown** tracked via `PhaseState.last_observe_rss` (**90m**) — **no** hour-of-day guard logic.
3. Subprocess timeouts configured (reuse loop guard timeout semantics or bespoke longer timeout documented in impl).
4. Non-zero **`r2e`** exit must map to surfaced **failure path** consistent with Beckett runner exit semantics (severity per policy).
5. Successful completion updates **`last_observe_rss`**.
6. **No LLM** usage.

### Soft constraints

- Warn when `PATH` lacks `r2e` executable even if cfg exists — doctor-level discoverability optional extension.

---

## Proposal format

### 1. Overview

Feeds land in inbox per r2e user configuration — Beckett observes side effects indirectly on later email-oriented phases.

### 2. Guard

Validates cfg path existence + parses PhaseState timestamps as timezone-aware or naive consistently with serializer.

### 3. Runner path

Stdout capture strategy; deterministic integer parsing fallback when metrics unavailable (`feeds_polled := 1` sentinel).

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-R1 | Config gate | Missing cfg ⇒ guard triggers false |
| M-R2 | Interval | Exact 90m comparison vs `last_observe_rss` |
| M-R3 | Invocation | Runs `r2e run` (argv captured in tests via stub) |
| M-R4 | PhaseState bump | Successful run persists timestamp |
| M-R5 | Pure shell | Implementation imports no pydantic-ai agent |
