# Beckett Loop Specification

**Implementation:** `cli/beckett/loop/`  
**Date:** 2026-04-30

---

## Scope

`beckett loop` is the canonical headless runtime for Pirandello roles. It evaluates guard conditions, invokes Pydantic AI agents or delegated subprocesses, manages memory writes, and commits changes — all without user interaction.

---

## Configuration

- Loop configuration is required as a `LoopSpec`.
- Loading precedence:
  1. `--spec <path>` (explicit override; requires `--role-target`)
  2. `<role>/loop.yaml` or `<role>/loop.yml`
  3. `<role>/loop.json`
  4. `<role>/loop.py` exposing `LOOP_SPEC: LoopSpec`
- `OODA.md` is not supported as runtime input. Roles with only `OODA.md` fail `beckett doctor`.

### LoopSpec structure

```yaml
observe:
  entries:
    - id: beckett-observe
      agent: beckett-observe        # registry key for agent function
      guard: beckett-observe        # registry key for guard function (defaults to id)
    - id: beckett-observe-rss
      agent: beckett-observe-rss
orient:
  entries:
    - id: beckett-orient-decisions
      agent: beckett-orient-decisions
act:
  entries:
    - id: beckett-act
      agent: beckett-act
active_hours: "07:00-19:00"     # optional daemon-mode gate (HH:MM-HH:MM)
interval_minutes: 15             # optional daemon interval (default 15)
```

---

## Decision Rules

These ten rules determine where any piece of logic belongs. Apply in order — the first matching rule wins.

| # | Rule | Binding |
|---|------|---------|
| 1 | Scheduling and eligibility conditions | Pydantic `GuardFn` |
| 2 | Pirandello mask scoping (role identity, env, MASKS_BASE) | `RoleDeps` |
| 3 | Side effects with hard invariants (write only within `role_dir/Memory/`) | Pydantic `@tool` |
| 4 | Deterministic API calls (count unread, list tasks, read file by path) | Pydantic `@tool` |
| 5 | Reading unstructured content and making a judgment | Direct LLM or `run_claude_skill` |
| 6 | Capabilities requiring multi-step agentic work with MCP access | `invoke_claude_agent` |
| 7 | Post-execution side effects (stamps, log updates, `last-run.json`, git, PhaseState persistence) | Pydantic runner |
| 8 | Cross-phase context propagation | `context: dict` + typed output models |
| 9 | Error handling and retry | Pydantic AI retry / runner error handling |
| 10 | "Can a Python function under 15 lines do this correctly?" | If yes: `@tool`; if no: LLM |

**Implementation files:** `cli/beckett/loop/claude.py`, `cli/beckett/loop/skill_agent.py`, `cli/beckett/loop/runner.py`, `cli/beckett/loop/phase_state.py`, `cli/beckett/loop/skills/*.py`

---

## Agent Architecture (Three Tiers)

Each registered skill is composed of a **guard function** and an **agent function**. The agent function uses one or more of three tiers:

### Tier 1 — Pydantic `@tool` (Rules 3, 4)

Python functions registered on a `pydantic_ai.Agent` using the `@agent.tool` decorator. The model calls these for deterministic data fetches and invariant-enforced writes. They do not invoke any LLM.

Examples:

- `get_unread_emails(account)` — calls `gws gmail triage`
- `write_memory_file(subpath, content)` — enforces write within `role_dir/Memory/`
- `complete_todoist_task(task_id)` — calls `td complete` (irreversible; Python must control)
- `apply_gmail_label(email_id, label)` — enforces valid label set before calling `gws`

### Tier 2 — Direct LLM Reasoning

The `pydantic_ai.Agent` model reasons over tool outputs using `BECKETT_MODEL`. Used when data is already structured but a judgment is needed (e.g., classify an email body, draft an observation entry, synthesize patterns from markdown files).

When `BECKETT_MODEL` is not set but `BECKETT_LLM_CMD` is configured, agents fall back to calling `invoke_claude` directly with a canned prompt (the subprocess fallback path). When neither is set, the agent logs a warning and returns the `fallback_result`.

### Tier 3 — `invoke_claude_agent`

For phases requiring **multi-step agentic work with MCP tool access**, the runner calls the Claude CLI in agent mode rather than piping a single prompt through `invoke_claude`.

- **Argv shape:**  
  `claude -p --agent <name> --plugin-dir <beckett_data_dir> --permission-mode auto --output-format json --max-budget-usd <budget>`
- **`cwd`:** `deps.role_dir` (role workspace root — all relative paths resolve as the role intends).
- **`beckett_data_dir`:** Resolved at import time via  
  `importlib.resources.files("beckett").joinpath("_data")`  
  so bundled agents and skills ship with the package.
- **`--plugin-dir`:** Makes all bundled agents and skills discoverable **without copying** artifacts into `~/.claude/`.

Pydantic-layer agents may still expose a **`run_claude_skill`** `@tool` that delegates to the Tier-2 **`invoke_claude`** stdin prompt stack where MCP breadth is unnecessary; **`invoke_claude_agent`** applies when Rule 6 multi-step MCP work is required.

---

## LLM Invocation Chain

`invoke_claude(deps, skill_prompt)` in `cli/beckett/loop/claude.py` (Tier-2 / `run_claude_skill` path):

1. **Builds the Pirandello prompt stack** by reading optional files in `hooks/start.sh` section order:
   - `=== GLOBAL AGENTS ===` — `<masks_base>/AGENTS.md`
   - `=== SELF ===` — `<masks_base>/personal/SELF.md`
   - `=== ROLE ===` — `<role_dir>/ROLE.md`
   - `=== ROLE AGENTS ===` — `<role_dir>/AGENTS.md`
   - `=== CONTEXT ===` — `<role_dir>/CONTEXT.md`
   - `=== ARCHIVE INDEX ===` — `<role_dir>/Archive/INDEX.md`
   - `=== MEMORY INDEX ===` — `<role_dir>/Memory/INDEX.md`
   - `=== REFERENCE INDEX ===` — `<role_dir>/Reference/INDEX.md`
2. Concatenates `stack + "\n---\n" + skill_prompt` as subprocess stdin.
3. Merges role env vars into subprocess env: `MASKS_BASE`, `MASKS_ROLE`, `MASKS_ROLE_DIR`, `BECKETT_ROLE`, `BECKETT_ROLE_DIR`.
4. Resolves command via `_llm_argv(deps)`: `BECKETT_LLM_CMD` → `MASKS_LLM_CMD` → `["claude", "--print", "--output-format", "text"]`.
5. If `BECKETT_OPENSHELL_POLICY` is set, wraps with `openshell run --policy <file> --`.
6. If `BECKETT_LLM_DEBUG=1`, captures subprocess stderr and logs it at `DEBUG` level.
7. Non-zero exit is logged at `WARNING` but not raised (matching legacy `run_cmd.py` behavior).

**Timeout:** `BECKETT_LLM_TIMEOUT` env var; default `1800` seconds; `0` = unlimited.

---

## Guard Evaluation (Two-Pass)

Each phase uses a two-pass evaluation strategy (closes the cross-skill awareness gap from the legacy single-pass model):

**Pass 1:** All guard functions in the phase are evaluated in declaration order. Results are collected in `trigger_map: dict[str, GuardOutcome]`. The full map is stored as `context["_phase_triggers"]`.

**Pass 2:** For each triggered entry (in order), the agent function is called with `context` containing `_phase_triggers` — so every agent can see what else fired in the same phase.

### Guard timeout

Each guard subprocess call respects `BECKETT_GUARD_TIMEOUT` / `MASKS_GUARD_TIMEOUT` from `deps.env`. Default: **5 seconds** (matching `run_cmd.py`). Timeout exceptions are caught; the entry is marked not triggered.

### Registry leniency

If a guard or agent ID from the `LoopSpec` is not found in the Python registry, a warning is logged and the entry is **skipped** (`skipped=true` in `last-run.json`). The cycle continues. This matches the old `name:X` behavior.

---

## Skill Contracts

Each built-in Beckett phase has a typed Pydantic output model. The model is returned from `agent.run()` / subprocess handling and stored in `SkillRunResult.agent_result`.

| Skill ID | Guard trigger condition | Agent type | Output model |
|---|---|---|---|
| `beckett-observe` | Unread email OR `.beckett-pending/observer.txt` present OR 90m elapsed since `last_observe` | Pydantic AI | `ObserveResult(signals_found, files_written, sources)` |
| `beckett-observe-rss` | r2e configured + 90m elapsed since `last_observe_rss` | Shell subprocess | `RssResult(feeds_polled, items_found)` |
| `beckett-observe-context-refresh` | 72h elapsed since `last_observe_context_refresh` | `invoke_claude_agent` | `ContextRefreshResult(files_reviewed, updated)` |
| `beckett-orient-decisions` | 30m elapsed since `last_orient_decisions` + new observation batch since last run | `invoke_claude_agent` | `DecisionsResult(decisions_synthesized, written)` |
| `beckett-orient-email` | 15m elapsed since `last_orient_email` + inbox-guard passes on ≥1 account | `invoke_claude_agent` per account (parallel) | `EmailOrientResult(accounts_processed, classified)` |
| `beckett-orient-hygiene` | 20m elapsed since `last_orient_hygiene` + `reply_needed` label exists in inbox | `invoke_claude_agent` | `HygieneResult(threads_reviewed, actions_taken)` |
| `beckett-orient-reply-drafter` | 15m elapsed since `last_orient_reply_drafter` + orient-email ran + `reply_needed` without draft | `invoke_claude_agent` | `ReplyDraftResult(drafts_created)` |
| `beckett-orient-todo-forwarder` | 15m elapsed since `last_orient_todo_forwarder` + unforwarded `todo` emails exist | Pure Python | `TodoForwardResult(forwarded, failed)` |
| `beckett-orient-meeting-prep` | 30m elapsed since `last_orient_meeting_prep` + qualifying upcoming meetings | `invoke_claude_agent` per meeting (parallel) | `MeetingPrepResult(meetings_prepped)` |
| `beckett-orient-post-meeting` | 30m elapsed since `last_orient_post_meeting` + meetings ended in past 90m + event-ID dedup | `invoke_claude_agent` | `PostMeetingResult(meetings_processed, tasks_created)` |
| `beckett-act` | Active `@agent`-labeled OR qualifying `@decision` Todoist tasks | Pydantic AI | `ActResult(executed, failed, task_ids)` |
| `beckett-scheduled-staff-update-draft` | Friday + 7d elapsed since `last_scheduled_staff_update` | `invoke_claude_agent` | `ScheduledResult(completed)` |
| `beckett-scheduled-efficiency-log` | Weekday + 24h elapsed since `last_scheduled_efficiency_log` | Shell | `ScheduledResult(completed)` |
| `beckett-scheduled-efficiency-email` | Weekday + 24h elapsed since `last_scheduled_efficiency_email` + log written today | Shell | `ScheduledResult(completed)` |
| `beckett-scheduled-desktop-archive` | 24h elapsed since `last_scheduled_desktop_archive` | `invoke_claude_agent` | `ScheduledResult(completed)` |

**Shared tools** registered on Pydantic agents where applicable: `run_claude_skill`, `write_memory_file`, `read_memory_file`, `search_memory`.

---

## Memory Contract

- Canonical memory store: markdown files under `<role_dir>/Memory/`.
- Semantic search: `mcp_memory_service.SqliteVecMemoryStorage` against `MCP_MEMORY_DB_PATH`.
- Write invariant: `write_memory(deps, subpath, content)` enforces `target.resolve().relative_to(role_dir/Memory/)`. Cross-role writes are rejected with `MemoryWriteError` except synthesis writes from the `personal` role to `personal/Memory/Synthesis/` (requires `allow_personal_synthesis=True`).
- Index: `Memory/INDEX.md` is created or preserved on every memory write.
- Git commit: at end of each cycle, `git add -A && git commit` (conditional on staged changes).
- Post-commit hook: `masks index` updates the memory search database when memory files change.

---

## OpenShell Sandboxing (Optional)

When `BECKETT_OPENSHELL_POLICY=<path>` is set, `invoke_claude` wraps the LLM subprocess:

```
openshell run --policy <path> -- <llm_cmd> ...
```

- **Container runtime:** Docker Engine 28.04+ (official) or Podman via `$DOCKER_HOST` / `$CONTAINER_HOST` / socket auto-detection.
- **Policy template:** `cli/beckett/_data/beckett-agent.yaml.example` — copy and substitute `{role_dir}` before use.
- **Doctor check:** when `BECKETT_OPENSHELL_POLICY` is set, `beckett doctor` adds an `openshell` check verifying the binary is on PATH and the container daemon is reachable. Status is `warn` (never `fail`) — the loop runs unsandboxed if OpenShell is misconfigured.
- **No-op when unset:** behavior is identical to the unsandboxed path.

---

## Execution Model

For each cycle:

1. Resolve role directories (explicit `--role-target` or `MASKS_BASE` discovery).
2. For each role: load `LoopSpec`, build `RoleDeps` (merges env from `os.environ → parent/.env → role/.env`), load **`PhaseState`** from disk into `deps.phase_state` (see **PhaseState** below).
3. Validate registry (lenient — warns and skips unresolved entries).
4. Check `active_hours` gate (daemon mode only).
5. For each phase (`observe → orient → act`):
   - Pass 1: evaluate all guards → `trigger_map`
   - Pass 2: for each triggered entry, run agent with `context` containing `_phase_triggers`
6. After each triggered agent completes: persist **`PhaseState`** (updated timestamps / dedup sets) to `<role_dir>/.beckett-state/phase-state.json`.
7. Write `<role>/.beckett-state/last-run.json`.
8. Stage and commit role changes.
9. Continue to next role on error (roles are independent).

### PhaseState

- **`PhaseState`** Pydantic model lives in **`cli/beckett/loop/phase_state.py`**.
- **Fields (`Optional[datetime]` unless noted):** last-run timestamps for each phase —
  `last_observe`, `last_observe_rss`, `last_observe_context_refresh`,
  `last_orient_decisions`, `last_orient_email`, `last_orient_hygiene`,
  `last_orient_reply_drafter`, `last_orient_todo_forwarder`, `last_orient_meeting_prep`,
  `last_orient_post_meeting`, `last_act`,
  `last_scheduled_staff_update`, `last_scheduled_efficiency_log`,
  `last_scheduled_efficiency_email`, `last_scheduled_desktop_archive`.

  Additional PhaseState payloads (e.g. event-ID dedup sets for meeting prep/post-meeting) are implementation-defined extensions of the same file.
- **Persistence path:** `<role_dir>/.beckett-state/phase-state.json`.
- **Load site:** `build_role_deps` reads PhaseState during dependency construction.
- **Storage site:** Runner exposes `deps.phase_state`; guards read interval eligibility from these timestamps (**Guard Contract**, below).

---

## Exit Codes

| Code | Condition |
|---|---|
| `0` | No fatal errors; no partial agent failures |
| `1` | One or more fatal configuration or dependency errors |
| `2` | No fatals, but one or more agent execution failures |

---

## CLI Surface

### `beckett loop`

```
beckett loop [OPTIONS]

Options:
  --role-target TEXT   Role path or name. Omit to run all roles under MASKS_BASE.
  --once               Run one cycle and exit.
  --dry-run            Evaluate guards only — print trigger table without running agents.
  --skill TEXT         Run a single skill by entry ID (implies --once). Requires --role-target.
  --force              With --skill: run agent even if guard does not trigger.
  --interval TEXT      Daemon loop interval (e.g. 5m, 30s, 1h). Default: 15m.
  --spec TEXT          LoopSpec path override. Requires --role-target.
```

**`--dry-run`:** evaluates all guards and prints a trigger table. No agents are invoked, no files written (including PhaseState updates), no git commit. Useful for verifying guard logic without spending tokens.

**`--skill <id>`:** runs a single skill's guard+agent cycle. With `--force`, the agent runs regardless of guard outcome. Prints guard result, agent result dict, and committed status.

**`BECKETT_LOOP_INTERVAL`:** env var overrides `--interval` in daemon mode.

### `beckett doctor`

Validates `loop_spec`, `registry`, `model_env` (warn-only), and `openshell` (warn-only, only when `BECKETT_OPENSHELL_POLICY` is set).

### `beckett roles`

Reports LoopSpec source per role: `loop.yaml` / `loop.json` / `loop.py` / `OODA.md (unsupported)` / `missing`.

### `beckett status`

```
beckett status [OPTIONS] [ROLE_TARGETS]...

Options:
  --verbose / -v   Show full per-phase, per-skill breakdown from last-run.json.
```

Without `--verbose`: compact tabular summary (role, last run timestamp, triggered count, success).  
With `--verbose`: full per-phase, per-skill detail including guard outcome, `▶`/`·` icons, agent result fields, and error strings.

---

## Naming Convention

All Beckett-owned artifacts use the **`beckett-` prefix** without exception: phase IDs, agent `.md` definitions, bundled skill directories, and dotfile state directories (`<role_dir>/.beckett-state/`, `.beckett-pending/`). Third-party tools, Claude defaults under `~/.claude/`, and non-Beckett plugins are unaffected.

---

## Guard Contract

- Guards rely on **interval-based cooldowns** recorded in **`PhaseState`** timestamps only — no built-in operational-hours predicates inside guard functions themselves.
- If working-hours restriction is desired, **`active_hours` in `loop.yaml`** is the single supported gate before cycles run (`Execution Model`, step 4). This deliberately **deviates** from legacy `agent-skills` conventions that folded business-hour logic into guards.

---

## Architectural Decisions

Recorded design choices for the Beckett loop surface:

| Decision | Rationale |
|---|---|
| **Per-role `PhaseState`** (stored under `<role_dir>/.beckett-state/`, not global dotfiles in `$HOME`) | Keeps telemetry and cooldowns co-located with the role workspace and avoids cross-role coupling. |
| **`cwd = role_dir` for Claude agent invocation** | Relative paths (`Memory/`, `CONTEXT.md`) and subprocess tools resolve consistently per Pirandello role layout. |
| **`--plugin-dir` points at bundled `beckett/_data`** | Ships agents/skills with the package; eliminates a separate install step into `~/.claude/agents/` or `~/.claude/skills/`. |
| **`beckett-` prefix universal** | Unambiguous identities in CLI, YAML, telemetry, and agent skill discovery. |
| **Parallel dispatch via `ThreadPoolExecutor`** in agent functions **only** (e.g., per-account email orient, per-meeting prep) | Parallelism scoped to deterministic fan-out orchestration layers; avoids nested concurrent runner complexity. |
| **LLM vs pure-Python splits** | Deterministic transports (RFC 822 forward, Gmail label predicates) remain **pure Python without LLM** for idempotence and auditability (`beckett-orient-todo-forwarder`); MCP-heavy workflows use **`invoke_claude_agent`**. |

---

## Environment Variables

| Variable | Effect | Default |
|---|---|---|
| `MASKS_BASE` | Parent directory of role directories | Desktop or home |
| `BECKETT_MODEL` | Pydantic AI model string (e.g. `openai:gpt-4o`) | None |
| `BECKETT_LLM_CMD` | Override LLM subprocess command | `claude --print --output-format text` |
| `MASKS_LLM_CMD` | Fallback LLM command override | Same as above |
| `BECKETT_LLM_TIMEOUT` | LLM subprocess timeout in seconds; `0` = unlimited | `1800` |
| `BECKETT_LLM_DEBUG` | Set `1` to log LLM subprocess stderr at DEBUG | off |
| `BECKETT_GUARD_TIMEOUT` | Guard subprocess timeout in seconds | `5` |
| `MASKS_GUARD_TIMEOUT` | Fallback guard timeout | `5` |
| `BECKETT_OPENSHELL_POLICY` | Path to OpenShell policy YAML; enables sandboxing | unset |
| `BECKETT_LOOP_INTERVAL` | Daemon interval override | value of `--interval` |
| `BECKETT_AGENT_BUDGET_USD` | Max USD per `invoke_claude_agent` subprocess (`--max-budget-usd`) | `2.00` |
| `MCP_MEMORY_DB_PATH` | Path to SQLite-vec memory database | `~/.pirandello/memory.db` |
| `SYNTHESIS_DAY` | Day-of-week for synthesis guard (0=Sunday) | `0` |
| `DAILY_BRIEFER_TARGET` | Target time for daily briefer guard (HH:MM) | `06:45` |
| `GWS_PROFILE` | Google Workspace account identifier for gws CLI | role name |
