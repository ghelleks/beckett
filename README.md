# Beckett

Beckett provides a Pirandello-aware **Pydantic AI loop runtime**.

- Canonical command: `beckett loop`
- Configuration source: role-local `loop.yaml` / `loop.json` / `loop.py`
- Canonical memory store: filesystem `Memory/**/*.md`
- Semantic memory reads: `mcp_memory_service` SQLite-vec index

Legacy Prefect orchestration and `OODA.md` runtime inputs are removed from the active path.

## Install

```bash
cd cli
uv tool install .
```

## Core commands

- `beckett roles`
- `beckett doctor`
- `beckett status`
- `beckett loop`

## Loop usage

```bash
# all roles under MASKS_BASE, every 15 minutes
beckett loop

# single role daemon
beckett loop --role-target work

# one-shot run
beckett loop --once --role-target work

# custom interval
beckett loop --interval 5m
```

## References

- [docs/design.md](docs/design.md)
- [docs/specs/beckett-loop/SPEC.md](docs/specs/beckett-loop/SPEC.md)
- [docs/specs/beckett-loop/SCENARIOS.md](docs/specs/beckett-loop/SCENARIOS.md)

## License

MIT — see [LICENSE](LICENSE).