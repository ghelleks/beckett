# Beckett

Beckett runs the **OODA heartbeat** for Pirandello-style Role workspaces: parse `OODA.md`, run **pre-flight guards**, optionally invoke a **single non-interactive LLM** pass with OODA-only context, and append structured lines to `**.ooda.log`**.

**Pirandello** (the `masks` CLI) supplies setup, hooks, `masks index`, sync, reflect, and reference refresh. Beckett does **not** replace Pirandello; it complements it.

## Install

```bash
cd cli && uv tool install .
```

## Usage

```bash
# Preferred: explicit path to the Role directory (contains OODA.md)
beckett run ~/Desktop/masks-base/work

# Optional: bare name when MASKS_BASE is set (in env or Desktop/.env)
beckett run work

beckett doctor
beckett status
```

See [docs/design.md](docs/design.md) and [docs/specs/beckett-run/SPEC.md](docs/specs/beckett-run/SPEC.md). Orient synthesis skill: [skills/mask-ooda-orient-synthesis/SKILL.md](skills/mask-ooda-orient-synthesis/SKILL.md).

## Migration from `masks run`

See [MIGRATION.md](MIGRATION.md).

## License

MIT — see [LICENSE](LICENSE).