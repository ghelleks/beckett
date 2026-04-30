---
name: beckett-observe-rss
description: Shell-accompaniment agent for RSS — documents r2e expectations; primary work is subprocess r2e run from beckett-loop.
allowed-tools:
  - Read
  - Bash
---

This agent is informational when invoked interactively.

For automated loops, Beckett invokes `r2e run` in Python before/after optional agent notes. Never write outside `Memory/` in the active role unless asked.

If invoked: confirm `~/.config/rss2email/config.cfg` exists, suggest `r2e run`, and stop.
