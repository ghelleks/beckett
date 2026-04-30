---
name: beckett-observe-context-refresh
description: Refresh pod charter caches and persona/core memory canon from Google Drive (72h throttle in loop guard).
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Run only from the Pirandello role directory (`BECKETT_ROLE_DIR`).

1. Load **ROLE.md** and skim **CONTEXT.md**.
2. Run `/core-memory-refresh` and `/pod-context-refresh` (slash-command names from your environment) **if available**; otherwise read canonical persona/strategy charters from Drive per ROLE instructions and summarise updates.
3. Write short sync notes **only under `Memory/`** (never Reference or repo roots).

Finish with compact JSON `{ "files_reviewed": N, "updated": N }` on stdout.
