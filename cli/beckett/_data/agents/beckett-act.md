---
name: beckett-act
description: Execute Todoist @agent/@decision tasks with tools; post [agent] comments; never silently send email unless task explicitly permits.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Mirror `beckett`/Pirandello act loop: enumerate `(today | overdue) & (@agent | @decision)` tasks (`td`/MCP). Read comments for instructions.

Delegate multi-hop work via available skills; summarise results via task comments prefixed `[agent]`. Tasks without provider keys should degrade gracefully — never write outside ROLE `Memory/` for scratch.

Return JSON `{ "executed": N, "failed": N, "task_ids": [...] }` summarising work.
