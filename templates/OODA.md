# OODA — [role-name]

**Active hours:** 09:00–17:00 America/New_York, weekdays

---

## Signal Sources

- Calendar: `gws --account` using `GWS_PROFILE` from this Role's `.env` (install **gws** separately; tokens live in gws config)
- Gmail: same — `gws --account "$GWS_PROFILE"`
- Todoist: projects labeled `#[role]`

**Observations write to:** Memory/ (tag: `[role]`)
**Cross-cutting synthesis writes to:** personal/Memory/

---

## Agenda

Runs every 15 minutes during active hours.
Pre-flight guards run before any LLM is invoked — if all fail, logs OODA_OK and exits.

### Observe

1. `ooda-observe`

### Orient

1. `email-classifier`

### Act

1. `daily-briefer`
2. `ooda-act`

Convention: Orient is for synthesizing observations into understanding or decisions. Scheduled maintenance tasks that fetch, refresh, or output content belong in Act.

---

## Excluded

- (List signal sources this Role's loop must not touch)