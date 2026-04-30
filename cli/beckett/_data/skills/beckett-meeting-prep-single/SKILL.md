---
name: beckett-meeting-prep-single
description: Single-meeting deep prep orchestrated by beckett-meeting-preparer harness (event_id anchored).
---

# Beckett Meeting Prep Single

`/beckett-meeting-prep-single` follows Pirandello `meeting-prep-single` sequencing:

## Harness Inputs

Prefer explicit `event_id`, `todoist_task_content`, `todoist_task_due` emitted by beckett-loop — avoid redundant calendar guessing.

## Flow

1. Pull calendar event (`gws calendar`) unless payload already includes event JSON.
2. Determine meeting archetype + stakeholders.
3. Read linked agendas/docs from URLs in event description (`gws drive`/`docs` exporters).
4. Crosswalk Todoist `@next`/`p1/p2` context via MCP or `td`.
5. Output prep brief + talking points + follow-up stubs; Todoist descriptions **must retain** trailing `event_id: <calendar id>`.

Return JSON snippets when beckett tooling requests machine-readable completions.
