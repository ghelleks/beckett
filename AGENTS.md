# Beckett — contributor conventions

This is the **development repo** for the Beckett OODA runner.

## Bundled assets live in `cli/beckett/_data/`

Guard scripts and `templates/OODA.md` are bundled inside the Python package. `resolve_framework_root()` returns that `_data/` path — do not walk the filesystem to find a framework root.

## Copy, never symlink

If you add a distribution step that copies guards to user-owned paths, use copies (same policy as Pirandello). The default runner uses bundled guards from the wheel.

## Authoring layout

- Canonical shell scripts: repo-root `guards/*.sh`
- Canonical template: `templates/OODA.md`
- After editing, sync into `cli/beckett/_data/` before release (or rely on your copy script).

## Docs

`docs/design.md` is the authoritative product description. `docs/specs/*/SPEC.md` and `SCENARIOS.md` are contracts for behavior.
