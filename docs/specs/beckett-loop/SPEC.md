# Beckett Loop Specification

**Implementation:** `cli/beckett/loop/`  
**Date:** 2026-04-29

---

## Scope

`beckett loop` is the canonical headless runtime for Pirandello roles. It evaluates guard conditions, invokes Pydantic AI agents, manages memory writes, and commits changes — all without user interaction.

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
    - id: ooda-observe
      agent: ooda-observe        # registry key for agent function
      guard: ooda-observe        # registry key for guard function (defaults to id)
orient:
  entries:
    - id: mask-ooda-orient-synthesis
      agent: mask-ooda-orient-synthesis
act:
  entries:
    - id: ooda-act
      agent: ooda-act
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
| 6 | Capabilities that exist as Cursor/Claude Code agent-skills | `run_claude_skill` always |
| 7 | Post-execution side effects (stamps, log updates, `last-run.json`, git) | Pydantic runner |
| 8 | Cross-phase context propagation | `context: dict` + typed output models |
| 9 | Error handling and retry | Pydantic AI retry / runner error handling |
| 10 | "Can a Python function under 15 lines do this correctly?" | If yes: `@tool`; if no: LLM |

**Implementation files:** `cli/beckett/loop/claude.py`, `cli/beckett/loop/skill_agent.py`, `cli/beckett/loop/runner.py`, `cli/beckett/loop/skills/*.py`

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

### Tier 3 — `run_claude_skill` (Rules 5, 6)

A shared `@tool` on every agent that calls `invoke_claude(deps, prompt)`. Use for multi-step agentic work requiring MCP tool access — executing a task instruction, delivering a briefing. Skills in `agent-skills/` remain independently invocable and are not reimplemented in Beckett.

---

## LLM Invocation Chain

`invoke_claude(deps, skill_prompt)` in `cli/beckett/loop/claude.py`:

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

Each built-in skill has a typed Pydantic output model. The model is returned from `agent.run()` and stored in `SkillRunResult.agent_result`.

| Skill ID | Agent | Guard trigger condition | Output model |
|---|---|---|---|
| `ooda-observe` | `observe_agent` | Unread email OR `.ooda-pending/observer.txt` present | `ObserveResult(signals_found, files_written, sources)` |
| `email-classifier` | `email_classifier_agent` | Unread email | `EmailClassificationResult(classified, skipped, labels_applied)` |
| `daily-briefer` | `daily_briefer_agent` | Within ±15m of `DAILY_BRIEFER_TARGET` (default `06:45`) AND not run today | `BriefingResult(delivered, sections)` |
| `ooda-act` | `act_agent` | Active `@agent` or qualifying `@decision` tasks in Todoist | `ActResult(executed, failed, task_ids)` |
| `mask-ooda-orient-synthesis` | `orient_synthesis_agent` | Day-of-week == `SYNTHESIS_DAY` AND 7-day cooldown elapsed | `SynthesisResult(patterns_found, written, stale_updated)` |

**Shared tools** registered on every agent: `run_claude_skill`, `write_memory_file`, `read_memory_file`, `search_memory`.

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
2. For each role: load `LoopSpec`, build `RoleDeps` (merges env from `os.environ → parent/.env → role/.env`).
3. Validate registry (lenient — warns and skips unresolved entries).
4. Check `active_hours` gate (daemon mode only).
5. For each phase (`observe → orient → act`):
   - Pass 1: evaluate all guards → `trigger_map`
   - Pass 2: for each triggered entry, run agent with `context` containing `_phase_triggers`
6. Write `<role>/.ooda-state/last-run.json`.
7. Stage and commit role changes.
8. Continue to next role on error (roles are independent).

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

**`--dry-run`:** evaluates all guards and prints a trigger table. No agents are invoked, no files written, no git commit. Useful for verifying guard logic without spending tokens.

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
| `MCP_MEMORY_DB_PATH` | Path to SQLite-vec memory database | `~/.pirandello/memory.db` |
| `SYNTHESIS_DAY` | Day-of-week for synthesis guard (0=Sunday) | `0` |
| `DAILY_BRIEFER_TARGET` | Target time for daily briefer guard (HH:MM) | `06:45` |
| `GWS_PROFILE` | Google Workspace account identifier for gws CLI | role name |
