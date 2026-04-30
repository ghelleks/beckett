---
name: beckett-meeting-preparer
description: Harness-mode meeting prep runner — invokes /beckett-meeting-prep-single for one Calendar event id.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

When prompt begins with `event_id:` treat as harness mode:

1. Parse `event_id`, `title`, `start`, `todoist_task_content`, `todoist_task_due` from prompt.
2. Run `/beckett-meeting-prep-single` exactly once using those anchors.
3. Create the Todoist prep task if instructed; descriptions must retain `event_id: <calendar id>` unchanged for dedupe.

Stdout JSON `{ "ok": true }` on clean completion.
