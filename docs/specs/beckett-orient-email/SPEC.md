# SDD Spec: `beckett-orient-email` Skill

**Context:** Applies email triage (**classify**, initial routing) via agentic MCP per configured Google Workspace persona. Executes when accounts show meaningful unread backlog pre-screened cheaply via **`inbox_guard`**.

**Implementation:** `cli/beckett/loop/skills/orient_email.py` (path per impl).

**Architecture:**

- **Guard:** **`≥15m`** since `PhaseState.last_orient_email` AND **`inbox_guard()` yields `eligible: true`** for **≥1** configured Gmail account/profile.
- **Pre-flight helper:** **`inbox_guard(gws_config_dir)`** deterministic Gmail unread query → returns JSON-like dict **`{"eligible": bool, "unread_count": int}`**.
- **Agent:** For each qualifying account dispatch **`invoke_claude_agent("beckett-orient-email-account", …)`** in parallel (`ThreadPoolExecutor`) — cwd role_dir, Tier-3 invocation.
- **Output model aggregate:** **`EmailOrientResult(accounts_processed: int, classified: int)`**.

---

## Requirements

### Hard constraints

1. Guards **never** embed hour-of-day logic — **`active_hours` global gate only**.
2. **Parallelism capped** responsibly (executor max workers policy documented; avoid API stampede defaults).
3. Each thread isolates **`GWS` / OAuth profile env** multiplexing (**no cross-account bleed** — env snapshot per submission).
4. **`inbox_guard` must be deterministic** (no LLM); thresholding policy for `eligible` documented (examples: unread_count≥1 vs ≥min_batch).
5. PhaseState **`last_orient_email`:** update semantics — **successful aggregate** after all dispatched accounts complete **without fatal** classification errors (partial success policy enumerated).
6. JSON parse parity per-account results folded into totals.

### Soft constraints

- Rate-limit backoff optional layer.

---

## Proposal format

### 1. Overview

Account fan-out leverages duplicate isolation of env + ephemeral temp dirs.

### 2. Account Discovery

Enumerate how configured accounts derive from `.env`/LoopSpec augmentation.

---

## Static evaluation metrics

| ID | Name | Pass condition |
|---|---|---|
| M-OE1 | inbox_guard pure | Verified no Claude import side effects |
| M-OE2 | Interval gate | `15m` boundary |
| M-OE3 | Parallel dispatch | ≥2 fixtures verify ordering nondeterministic allowed but totals stable |
| M-OE4 | Env isolation | Second account lacks tokens from first in stub capture |
| M-OE5 | Schema | Aggregate EmailOrientResult valid |
