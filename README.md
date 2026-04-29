# Beckett

Beckett provides a Pirandello-aware **Pydantic AI loop runtime**.

- Canonical command: `beckett loop`
- Configuration source: role-local `loop.yaml` / `loop.json` / `loop.py`
- Canonical memory store: filesystem `Memory/**/*.md`
- Semantic memory reads: `mcp_memory_service` SQLite-vec index

## Quick start

```bash
# 1. Install
cd cli && uv tool install .

# 2. Create loop.yaml for all roles under MASKS_BASE
beckett install

# 3. Validate configuration
beckett doctor

# 4. Preview guard outcomes (no tokens spent)
beckett loop --dry-run

# 5. Run one full cycle
beckett loop --once --role-target work
```

See [docs/install.md](docs/install.md) for the full step-by-step guide.

## Core commands

| Command | Description |
|---|---|
| `beckett install` | Create `loop.yaml` for each role (non-destructive) |
| `beckett roles` | List roles and their spec status |
| `beckett doctor` | Validate loop specs, registry, and model env |
| `beckett status` | Show last run summary (`--verbose` for full breakdown) |
| `beckett loop` | Run the loop daemon or a single cycle |

## Loop usage

```bash
# Daemon — all roles, every 15 minutes
beckett loop

# Single role daemon
beckett loop --role-target work

# One-shot run
beckett loop --once --role-target work

# Preview guards without running agents
beckett loop --dry-run --role-target work

# Force a single skill to run
beckett loop --skill ooda-observe --role-target work --force
```

## References

- [docs/install.md](docs/install.md) — Installation and setup guide
- [docs/design.md](docs/design.md) — Architecture overview
- [docs/specs/beckett-loop/SPEC.md](docs/specs/beckett-loop/SPEC.md) — Loop specification
- [docs/specs/beckett-loop/SCENARIOS.md](docs/specs/beckett-loop/SCENARIOS.md) — Behavior scenarios

## License

MIT — see [LICENSE](LICENSE).
