# SDD Scenarios: `beckett run`

**Companion spec:** `docs/specs/beckett-run/SPEC.md`

Use cases and stress tests mirror the former Pirandello `masks-run` scenarios, with these substitutions:

- `masks run work` → `beckett run "$MASKS_BASE/work"` or `beckett run /absolute/path/to/work`
- Paths `$BASE/<role>/` → `<role_dir>/` as given on the CLI (resolved absolute directory)
- Metrics **M-01 … M-10** → **B-01 … B-10** (see SPEC.md)

### Path-first (new)

**P9 Explicit path from cron.** Cron runs `beckett run /Users/me/Desktop/masks-base/work` with `PWD=/`. The runner uses `/Users/me/Desktop/masks-base/work` as `role_dir` for `OODA.md`, `.env`, and `.ooda.log`.

Pass: behavior matches `masks run work` when `MASKS_BASE` is `.../masks-base` and role folder is `work`.

**P10 Bare name shorthand.** `MASKS_BASE` is set in the environment; `beckett run work` resolves to `$MASKS_BASE/work`.

Pass: same as P9 when that directory exists.
