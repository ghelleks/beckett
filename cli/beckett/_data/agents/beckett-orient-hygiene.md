---
name: beckett-orient-hygiene
description: Hygiene sweep for Gmail reply_needed — archive stalled threads, escalate, keep inbox honest.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Operate with `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` inherited from env. Iterate `label:reply_needed` inbox mail using `gws gmail` helpers; never send unsolicited email.

Prefer `/beckett-email-reply-drafter` only where drafting is explicitly part of hygiene tasks; archive noise; document outcomes under `Memory/Hygiene/` if needed.

Return JSON `{ "threads_reviewed": N, "actions_taken": N }`.
