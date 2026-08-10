---
layout: post
title: "How Guards Decide Whether There's Work to Do"
date: 2026-04-29
categories: [components]
excerpt: "In this post you will learn how Beckett's guard scripts work and how each bundled guard checks a real-world signal before deciding whether to invoke Claude."
---

## The Problem

Running an LLM every 15 minutes regardless of whether anything has changed is
wasteful. Most of the time your inbox hasn't grown, your task list hasn't
changed, and it's not time for a briefing. You want the runner to be
intelligent about when to act — cheap to run when there's nothing to do, and
reliably triggered when something real needs attention.

## The Component

**Guard scripts** are fast Bash scripts that each answer one binary question
about the world: "is there work right now?" Beckett runs every guard listed in
your **OODA.md** before considering an LLM call. Only when at least one guard
reports that work exists does Claude get invoked. Guards are the pre-flight
decision layer — they keep your cron job cheap and focused.

## How It Works

- A guard exits **0** to signal "there is work for the LLM"; it exits
  **non-zero** to signal "nothing to do right now."
- **All guards always run.** Beckett does not short-circuit on the first
  passing guard. This ensures every signal gets checked on every cycle,
  regardless of ordering in **OODA.md**.
- Guards run with a **5-second timeout.** A guard that hangs (e.g. a network
  call that never returns) is treated as "nothing to do" and the run continues.
- Guards receive environment variables from Beckett: `MASKS_ROLE_DIR`,
  `MASKS_BASE`, `MASKS_ROLE`, `GWS_PROFILE`, and everything from your merged
  `.env` files.
- Beckett ships five bundled guards:

| Guard | What it checks |
|-------|---------------|
| `ooda-observe` | New Gmail triage output via `gws`, or content in `.ooda-pending/observer.txt` |
| `email-classifier` | Unclassified Gmail items on your GWS account |
| `daily-briefer` | Whether it's 06:30–07:00 and the briefing hasn't run today |
| `ooda-act` | Todoist tasks tagged `@agent` or `@decision` that are due today or overdue |
| `mask-ooda-orient-synthesis` | Whether it's synthesis day (default Sunday) and 7+ days since last synthesis |

## Walkthrough

**1. Confirm your guards are installed and executable.**

```bash
$ beckett doctor ~/Desktop/masks-base/work

[PASS] ooda_agenda: all roles parseable
[PASS] guards_executable: all guards present
```

**2. Set the environment variables a guard needs, then run it manually.**

The `ooda-act` guard checks Todoist for tasks tagged `@agent` or `@decision`
due today or overdue. Run it directly to see whether it finds work:

```bash
$ export MASKS_ROLE_DIR=~/Desktop/masks-base/work
$ export MASKS_ROLE=work
$ guards/ooda-act.sh; echo "exit: $?"

exit: 1
```

Exit code 1 means no matching tasks were found — Beckett would skip the LLM
call for this guard. Now tag a Todoist task `@agent` with today's due date and
run it again:

```bash
$ guards/ooda-act.sh; echo "exit: $?"

Review Q2 budget proposal @agent
exit: 0
```

Exit code 0 means work exists. If `ooda-act` were the only guard in your
**OODA.md**, Beckett would invoke Claude on the next cycle.

**3. Check the `daily-briefer` guard's time-gating.**

The `daily-briefer` guard exits 0 only during the 30-minute window centered on
06:45 and only once per calendar day. Outside that window:

```bash
$ guards/daily-briefer.sh; echo "exit: $?"

exit: 1
```

The guard writes a stamp file at
`$ROLE_DIR/.ooda-state/daily-briefer-YYYY-MM-DD` after it triggers. Delete
the stamp to reset it for testing:

```bash
$ rm ~/Desktop/masks-base/work/.ooda-state/daily-briefer-$(date +%Y-%m-%d)
```

**4. See how guard results appear in the log.**

After a `beckett run`, open `.ooda.log` to read the guard result codes:

```bash
$ tail -1 ~/Desktop/masks-base/work/.ooda.log

ts=2026-04-29T08:17:03-07:00 role=work guards=ooda-observe:1|email-classifier:1|daily-briefer:1|ooda-act:0 trigger=yes llm=yes
```

Each entry is `<slug>:<exit-code>`. A code of `0` triggered the LLM (`trigger=yes`).
A code of `X` means the guard was missing or not executable. A code of `T`
means the guard timed out.

## What You Get

You now understand how guards filter your cron cycle down to only the moments
when something real needs attention. Every bundled guard is a self-contained
Bash script you can read, copy, or adapt. If you need a new signal, write a
new script that exits 0 when it detects work and reference its slug in
**OODA.md** — no other changes needed.

## Further Reading

- [Defining What Your Role Cares About with OODA.md](/beckett/2026/04/28/ooda-md-your-roles-agenda.html) — how skill slugs are listed in the agenda
- [Running Your Role's OODA Heartbeat](/beckett/2026/04/30/beckett-run-the-heartbeat-loop.html) — how `beckett run` orchestrates guards and the LLM call
