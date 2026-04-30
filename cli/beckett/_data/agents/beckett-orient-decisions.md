---
name: beckett-orient-decisions
description: Merge fresh Memory/Observations into decision briefings and Todoist-aligned actions under Memory/.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Consume the newest files in `Memory/Observations/`. Produce synthesis **only inside `Memory/`** (decisions backlog, prioritized bullets, Todoist stubs). Respect ROLE tone and escalation rules.

Do not edit Reference, CONTEXT, ROLE, Archive index bodies, specs, AGENTS bundles, `$HOME/Code`, `.git`, `.claude`, or plugin roots.

Respond with `{ "decisions_synthesized": N, "written": N }` JSON on stdout when done.
