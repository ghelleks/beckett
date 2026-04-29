# Beckett — Installation and Setup

This guide walks through installing Beckett, configuring your Pirandello roles to use it, and verifying the loop is working correctly before running it live.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| [uv](https://docs.astral.sh/uv/) | Package manager — used to install Beckett |
| [Pirandello](https://github.com/ghelleks/pirandello) | Role management system — provides `MASKS_BASE`, role directories, and memory tools |
| `gws` CLI | Google Workspace CLI — used by observe, email-classifier, and daily-briefer guards |
| `td` CLI | Todoist CLI — used by act and daily-briefer guards |
| `claude` CLI | Anthropic Claude Code — default LLM subprocess (or set `BECKETT_LLM_CMD`) |
| `MASKS_BASE` | Set in `~/Desktop/.env` by Pirandello, or export manually |

---

## Step 1 — Install Beckett

```bash
cd /path/to/beckett/cli
uv tool install .
beckett --version
```

The `beckett` binary is installed to `~/.local/bin/`. Confirm it is on your PATH:

```bash
which beckett
```

---

## Step 2 — Configure MASKS_BASE

Beckett reads `MASKS_BASE` from your environment or from `~/Desktop/.env` (Pirandello's default base env file). Verify it resolves:

```bash
beckett roles
```

Expected output lists your role directories. If you see "No role directories found", set `MASKS_BASE` in your shell or add it to `~/Desktop/.env`:

```bash
echo "MASKS_BASE=/Users/you/Desktop" >> ~/Desktop/.env
```

---

## Step 3 — Create loop.yaml files

`beckett install` generates a `loop.yaml` for each role with all five built-in skills. It is **non-destructive** — roles that already have a `loop.yaml` are skipped.

```bash
# Preview what would be created (no files written)
beckett install --dry-run

# Create loop.yaml for all roles
beckett install

# Create for a single role only
beckett install work

# Overwrite existing loop.yaml files
beckett install --force
```

The generated `loop.yaml` includes all five built-in skills with inline comments:

```yaml
observe:
  entries:
    - id: ooda-observe
      agent: ooda-observe

orient:
  entries:
    - id: email-classifier
      agent: email-classifier
    # Uncomment for the personal role only:
    # - id: mask-ooda-orient-synthesis
    #   agent: mask-ooda-orient-synthesis

act:
  entries:
    - id: daily-briefer
      agent: daily-briefer
    - id: ooda-act
      agent: ooda-act

active_hours: "09:00-17:00"
interval_minutes: 15
```

**Edit the file** to remove entries your role does not need, or to adjust `active_hours` and `interval_minutes`.

For the `personal` role, uncomment `mask-ooda-orient-synthesis` in the `orient` section to enable weekly cross-role memory synthesis.

---

## Step 4 — Configure the LLM

Beckett needs a model to run agents. Set one of:

**Option A — Anthropic (Claude):**

```bash
# In ~/Desktop/.env or your shell profile
BECKETT_MODEL=anthropic:claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...
```

**Option B — OpenAI:**

```bash
BECKETT_MODEL=openai:gpt-4o
OPENAI_API_KEY=sk-...
```

**Option C — Custom LLM command** (for testing or non-default models):

```bash
BECKETT_LLM_CMD=/path/to/my-llm-wrapper.sh
```

When `BECKETT_LLM_CMD` is set it takes priority over `BECKETT_MODEL` for the subprocess delegation path.

---

## Step 5 — Validate configuration

```bash
beckett doctor
```

All three checks should pass or warn:

| Check | Meaning |
|---|---|
| `loop_spec: pass` | Every role has a valid `loop.yaml` |
| `registry: pass` | All skill IDs in `loop.yaml` are registered |
| `model_env: pass` | `BECKETT_MODEL` or a provider API key is set |

If `registry` fails, a skill ID in your `loop.yaml` is not built in to this version of Beckett. Either remove it or register a custom guard/agent.

---

## Step 6 — Dry-run (no tokens spent)

Preview which guards would fire right now without invoking any agents:

```bash
beckett loop --dry-run
```

Expected output:

```
[DRY RUN] role=work  2026-04-29T09:15:00+00:00

Phase: observe
  · ooda-observe          SKIP     'quiet'

Phase: orient
  · email-classifier      SKIP     'no unread'

Phase: act
  · daily-briefer         SKIP     'outside window ±15m at 06:45'
  · ooda-act              SKIP     'no actionable tasks'

Summary: 0 would trigger / 4 total
```

Guards show `▶ TRIGGER` when their conditions are met. Guards show `· SKIP` when not. No files are written and no LLM is called in dry-run mode.

---

## Step 7 — Test a single skill

Force a single skill's agent to run regardless of its guard:

```bash
beckett loop --skill ooda-observe --role-target work --force
```

This is the safest way to verify an agent works end-to-end. Output shows the guard result, the agent result dict, and whether a git commit was made.

---

## Step 8 — Check the result

```bash
beckett status --verbose --role-target work
```

Shows the full per-phase, per-skill breakdown from `.ooda-state/last-run.json`:

```
ROLE: work
  Last run:  2026-04-29T09:16:02+00:00
  Triggered: 1/4   Success: yes   Committed: yes

  Phase: observe
    ▶ ooda-observe          TRIGGER  'observer marker'   signals_found=1 files_written=1

  Phase: orient
    · email-classifier      SKIP     'no unread'

  Phase: act
    · daily-briefer         SKIP     'outside window ±15m at 06:45'
    · ooda-act              SKIP     'no actionable tasks'
```

---

## Step 9 — Run a full one-shot cycle

```bash
beckett loop --once --role-target work
```

Evaluates all guards and runs any triggered agents. Exits `0` on success.

---

## Step 10 — Start the daemon

```bash
# All roles, every 15 minutes (active_hours gate applies)
beckett loop

# Single role
beckett loop --role-target work

# Custom interval
beckett loop --interval 5m
```

Stop with `Ctrl+C` or `SIGTERM`. The daemon respects `active_hours` in `loop.yaml` — guards are skipped outside the configured window.

---

## Environment variable reference

| Variable | Default | Description |
|---|---|---|
| `MASKS_BASE` | Desktop or home | Parent directory of role directories |
| `BECKETT_MODEL` | none | Pydantic AI model string (e.g. `anthropic:claude-sonnet-4-5`) |
| `BECKETT_LLM_CMD` | `claude --print --output-format text` | Override LLM subprocess command |
| `BECKETT_LLM_TIMEOUT` | `1800` | LLM subprocess timeout in seconds; `0` = unlimited |
| `BECKETT_LLM_DEBUG` | off | Set `1` to log LLM subprocess stderr |
| `BECKETT_GUARD_TIMEOUT` | `5` | Guard subprocess timeout in seconds |
| `BECKETT_OPENSHELL_POLICY` | unset | Path to OpenShell policy YAML; enables sandboxing |
| `BECKETT_LOOP_INTERVAL` | value of `--interval` | Daemon interval override |
| `MCP_MEMORY_DB_PATH` | `~/.pirandello/memory.db` | Semantic memory index path |
| `SYNTHESIS_DAY` | `0` (Sunday) | Day-of-week for orient synthesis guard |
| `DAILY_BRIEFER_TARGET` | `06:45` | Target time for daily briefer guard (HH:MM) |
| `GWS_PROFILE` | role name | Google Workspace account identifier |

---

## Troubleshooting

**"No role directories found"** — `MASKS_BASE` is not set or points to an empty directory.

**`registry: fail`** — a skill ID in `loop.yaml` is not registered. Check spelling against the built-in IDs: `ooda-observe`, `email-classifier`, `daily-briefer`, `ooda-act`, `mask-ooda-orient-synthesis`.

**`model_env: warn`** — no LLM is configured. Guards still run (dry-run works), but agents will not invoke the model. Set `BECKETT_MODEL` or `BECKETT_LLM_CMD`.

**Guard always returns SKIP** — verify the guard condition is met (e.g. unread email exists, it is within the `DAILY_BRIEFER_TARGET` window, or the observer marker file exists). Use `beckett loop --skill <id> --force` to bypass the guard and test the agent directly.

**Agent returns stub result** — neither `BECKETT_MODEL` nor `BECKETT_LLM_CMD` is set, so agents return the fallback empty result. Configure a model.
