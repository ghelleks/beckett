# Beckett CLI

Install with [uv](https://github.com/astral-sh/uv):

```bash
cd cli && uv tool install .
```

## Getting started

```bash
# Create loop.yaml for all roles (non-destructive)
beckett install

# Validate configuration
beckett doctor

# Preview guard outcomes without spending tokens
beckett loop --dry-run

# Run one cycle
beckett loop --once --role-target work
```

See [../docs/install.md](../docs/install.md) for the full setup guide.

## Commands

```
beckett install     Create loop.yaml for each role under MASKS_BASE
beckett roles       List roles and loop spec status
beckett doctor      Validate loop specs, registry, and model environment
beckett status      Show last run summary (--verbose for full breakdown)
beckett loop        Run the loop daemon or a single cycle
```

## Loop options

```
beckett loop [OPTIONS]

  --role-target TEXT   Single role path or name (default: all roles)
  --once               Run one cycle and exit
  --dry-run            Evaluate guards only, no agents, no writes
  --skill TEXT         Run a single skill by entry ID (requires --role-target)
  --force              With --skill: run agent even if guard does not trigger
  --interval TEXT      Daemon interval, e.g. 5m, 30s, 1h (default: 15m)
  --spec TEXT          LoopSpec path override (requires --role-target)
```

## Key environment variables

| Variable | Description |
|---|---|
| `MASKS_BASE` | Parent directory of role directories |
| `BECKETT_MODEL` | Pydantic AI model string (e.g. `anthropic:claude-sonnet-4-5`) |
| `BECKETT_LLM_CMD` | Override LLM subprocess (default: `claude --print --output-format text`) |
| `BECKETT_LLM_DEBUG` | Set `1` to log LLM subprocess stderr |
| `BECKETT_GUARD_TIMEOUT` | Guard subprocess timeout in seconds (default: `5`) |
| `BECKETT_OPENSHELL_POLICY` | OpenShell policy YAML path; enables sandbox |
