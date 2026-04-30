---
name: beckett-orient-reply-drafter
description: Produce Gmail drafts for reply_needed conversations using /beckett-email-reply-drafter conventions.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Work only inside the selected profile (`GOOGLE_WORKSPACE_CLI_CONFIG_DIR`). Invoke `/beckett-email-reply-drafter` for each actionable thread needing a draft. Do **not** send mail without explicit approval; create drafts/Gmail placeholders only.

Log counts as JSON `{ "drafts_created": N }`.
