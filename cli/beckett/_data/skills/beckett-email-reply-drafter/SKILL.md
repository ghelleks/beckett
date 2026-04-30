---
name: beckett-email-reply-drafter
description: Produce Gmail drafts for reply_needed conversations under Beckett/Pirandello controls.
---

# Beckett Email Reply Drafter

`/beckett-email-reply-drafter` mirrors the production skill but **never sends** outbound mail unless the initiating Todoist/task explicitly permits send.

Procedure:

1. Load tone + escalation notes from ROLE + persona references (read-only).
2. Fetch body via `gws gmail`.
3. Draft reply into Gmail drafts or structured markdown for `[agent]` review.
4. Summarise drafts created as `{ "drafts_created": N }`.

Record durable learnings inside `Memory/Email/learnings/` when appropriate.
