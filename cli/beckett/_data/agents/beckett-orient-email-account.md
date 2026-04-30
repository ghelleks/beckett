---
name: beckett-orient-email-account
description: Single Gmail account classifier — invokes /beckett-email-classifier for one OAuth profile.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

The harness selects the account (`GOOGLE_WORKSPACE_CLI_CONFIG_DIR` is preset). Echo that path, then invoke `/beckett-email-classifier` for this inbox only.

Classify actionable mail with labels `reply_needed`, `review`, `todo`, `summarize`; never send mail autonomously. Write summaries only inside `Memory/` if required by the skill pipeline.

Stdout must end as JSON `{ "classified": N }`.
