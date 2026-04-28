# Skill: mask-ooda-orient-synthesis

Ships with **Beckett**. Register this skill in the personal role `LoopSpec` under **orient**. The loop runtime evaluates the `mask-ooda-orient-synthesis` guard function before invoking the synthesis agent.

**Orient** skill that exercises **global-read**: scan every Role’s `Memory/**/*.md`, detect cross-role patterns, write **only** to `personal/Memory/Synthesis/*.md` and update `personal/Memory/INDEX.md`.

## Workspace enforcement

- `basename($PWD)` must be `personal`.
- Require `ROLE.md` and `Memory/` — else warn to stderr and exit before reads/writes.

## Role discovery

`BASE="$(dirname "$PWD")"`. Enumerate immediate child directories of `BASE` whose names do not start with `.` and which contain `ROLE.md`. Sort names ASCII order.

## Evidence scan

For each Role `R`, read `BASE/R/Memory/**/*.md` recursively.

- **Exclude** `personal/Memory/Synthesis/` from *raw observation mining* (outputs, not evidence).
- Do not follow symlinks across Roles.

Infer **session date** per file (first match wins):

1. YAML front matter `session_date:` or `date:`
2. Body line `**Session date:** YYYY-MM-DD` or `**Observed:** YYYY-MM-DD`
3. `git -C BASE/R log -1 --format=%cs -- <relpath>`

## Pattern thresholds

For each proposed pattern cluster:

- Let `S` = distinct session dates; `R` = distinct Roles represented.
- Proceed only if `(S ≥ 3) ∨ (R ≥ 2)`.
- **Write to `personal/Memory/Synthesis/` only if `R ≥ 2`.** Otherwise emit a ROLE.md suggestion bullet in the run summary (no synthesis file).

## Output file template

Each synthesis file `personal/Memory/Synthesis/<kebab-name>.md`:

```markdown
# <Title Case Name>

**First observed:** YYYY-MM-DD
**Last updated:** YYYY-MM-DD
**Status:** current | stale

## Pattern

One neutral paragraph suitable for eventual `SELF.md` reflection.

## Evidence

- (role) YYYY-MM-DD — `Memory/...` — one-sentence observation
```

## Staleness

Patterns older than **90 days** without qualifying refresh → set `**Status:** stale` (do not delete files).

## Logging

Append exactly one line to `personal/.synthesis.log` on successful completion:

`SYNTHESIS <ISO-8601 UTC> — <N> patterns found, <M> updated`

## Git

This skill performs **no git commands** — session hooks commit results.
