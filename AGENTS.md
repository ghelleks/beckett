# Beckett — contributor conventions

This is the **development repo** for the Beckett loop runner.

## Bundled assets live in `cli/beckett/_data/`

Bundled templates and optional assets live inside the Python package. `resolve_framework_root()` returns that `_data/` path — do not walk the filesystem to find a framework root.

## Copy, never symlink

If you add a distribution step that copies assets to user-owned paths, use copies (same policy as Pirandello).

## Authoring layout

- Canonical runtime configuration: role-local `loop.yaml` / `loop.json` / `loop.py` (LoopSpec)
- Canonical template: `templates/OODA.md` is legacy reference only, not an executable runtime source
- After editing, sync into `cli/beckett/_data/` before release (or rely on your copy script).

## Docs

`docs/design.md` is the authoritative product description. `docs/specs/*/SPEC.md` and `SCENARIOS.md` are contracts for behavior.
