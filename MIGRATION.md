# Migrating from Pirandello `masks run`

If you used **`masks run <role>`** on an older Pirandello install, switch to **`beckett run`**:

| Before | After |
|--------|--------|
| `masks run work` | `beckett run "$MASKS_BASE/work"` or `beckett run /path/to/work` |
| Cron with `masks run` | Cron with `beckett run` and explicit paths recommended |

Install Beckett (`cd cli && uv tool install .`), upgrade Pirandello so hooks no longer deploy guards under `~/.pirandello/guards/`, and read Pirandello’s `MIGRATION.md` for the full checklist.
