---
name: beckett-email-classifier
description: Beckett Gmail classifier adapted from Pirandello email pipeline — classify inbox labels, apply PAR-aware slugs, never send mail silently.
---

# Beckett Email Classifier

`/beckett-email-classifier` executes the Pirandello work/personal Gmail triage playbook:

1. Read `ROLE.md` + persona guardrails (`Memory/` indexes only — never poke Reference unless ROLE demands it).
2. Ensure `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` exported for the harness-selected account profile.
3. Pull uncategorized unread mail via `gws gmail +triage` / `messages.list` equivalents.
4. Classify into Gmail labels `{reply_needed, review, todo, summarize}` optionally plus slug labels from PARA conventions if configured in ROLE.
5. Apply labels via `gws gmail messages modify`.
6. Log notable decisions as short bullets under `Memory/Email/` for orient agents.

Failsafe: degrade to action-only labels if Todoist/project context unavailable; emit JSON `{ "classified": N }` for tooling.
