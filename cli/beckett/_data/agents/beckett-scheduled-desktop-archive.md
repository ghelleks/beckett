---
name: beckett-scheduled-desktop-archive
description: Desktop housekeeping — run /desktop-archive for stale Cursor task dirs.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Ensure backup paths from ROLE before moving anything. Prefer `/desktop-archive` skill; log summary under `Memory/Housekeeping/`. Respond `{ "done": true }` when archives complete cleanly.
