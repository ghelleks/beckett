---
name: beckett-orient-post-meeting
description: Summarize recently ended meetings, capture decisions, enqueue follow-ups/Todoist work.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Combine Calendar + transcripts (per ROLE instructions) plus `Memory/Observations/`. Persist structured notes **under `Memory/Meetings/`** only; cite event ids referenced in prompts.

Produce compact JSON `{ "meetings_processed": N, "tasks_created": N }`.
