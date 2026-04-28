# Beckett CLI

Install with [uv](https://github.com/astral-sh/uv):

```bash
cd cli && uv tool install .
```

Then run `beckett --help`.

Primary commands:

- `beckett roles`
- `beckett doctor`
- `beckett status`
- `beckett loop`

`beckett loop` defaults to a 15-minute daemon cadence. Use `--once` for a single cycle.
Loop configuration is loaded from role-local `loop.yaml` / `loop.json` / `loop.py`.
