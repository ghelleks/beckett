---
layout: post
title: "Defining What Your Role Cares About with OODA.md"
date: 2026-04-28
categories: [components]
excerpt: "In this post you will learn how to write an OODA.md agenda file so that Beckett knows exactly which signals to watch and which tasks to perform for a role."
---

## The Problem

When you want an AI assistant to handle background work for a specific context
— processing your work inbox, triaging tasks, writing a daily briefing — you
need to tell it what that context cares about and what it should do. If you
have to re-explain this every time you invoke it, you haven't automated
anything. What you need is a persistent, structured description of the role
that the runner can read on every cycle.

## The Component

**OODA.md** is a markdown agenda file that lives in each Role directory.
Beckett reads it every cycle to know which guard scripts to run and what
context to hand to Claude when work is found. It is the single source of
truth for a role's autonomous behavior: what to observe, how to orient, and
what to act on.

## How It Works

- **OODA.md** contains three numbered sections: `### Observe`, `### Orient`,
  and `### Act`. Each section lists skill slugs — kebab-case identifiers like
  `ooda-observe` or `daily-briefer`.
- Each slug maps to a guard script at `guards/<slug>.sh`. When Beckett runs,
  it executes each guard in the order they appear in the file.
- Inline comments after ` — `, ` -- `, or ` # ` are stripped, so you can
  annotate items without affecting parsing.
- Backtick wrapping (`` `slug` ``) is accepted.
- Duplicate slugs are ignored after the first occurrence — the parser processes
  each skill exactly once, in document order.
- A slug must match `[a-z0-9][a-z0-9-]*` (lowercase, digits, hyphens only).
  Any item that doesn't match is skipped with a warning written to `.ooda.log`.

## Walkthrough

**1. Copy the bundled template into your role directory.**

```bash
$ cp "$(python3 -c 'import beckett; print(beckett.__file__.replace("__init__.py",""))')_data/templates/OODA.md" ~/Desktop/masks-base/work/OODA.md
```

Or copy it directly from the repository:

```bash
$ cp /path/to/beckett/templates/OODA.md ~/Desktop/masks-base/work/OODA.md
```

**2. Open the file and set the role name and active hours.**

The top of the template looks like this:

```markdown
# OODA — [role-name]

**Active hours:** 09:00–17:00 America/New_York, weekdays
```

Change `[role-name]` to match your role directory name and adjust the active
hours to your timezone and schedule. These lines are documentation only —
Beckett does not parse them. Time-gating happens inside guard scripts.

**3. Edit the Agenda sections.**

The template ships with a minimal set of skills. Here is a typical work-role
agenda:

```markdown
### Observe

1. `ooda-observe`

### Orient

1. `email-classifier`

### Act

1. `daily-briefer`
2. `ooda-act`
```

Remove any skill you don't need. Add skills by inserting a new numbered line
with the slug. The order within each section determines the order guards run.

**4. Validate the agenda parses correctly.**

```bash
$ beckett doctor ~/Desktop/masks-base/work

[PASS] ooda_agenda: all roles parseable
[PASS] guards_executable: all guards present
```

If you see a `[FAIL]` on `ooda_agenda`, open **OODA.md** and check that every
item under `### Observe`, `### Orient`, and `### Act` is a numbered list entry
(`1.`, `2.`, etc.) with a valid kebab-case slug.

**5. Confirm Beckett can find the file.**

```bash
$ beckett run ~/Desktop/masks-base/work
```

Look at the resulting log line:

```bash
$ tail -1 ~/Desktop/masks-base/work/.ooda.log

ts=2026-04-28T09:00:01-07:00 role=work guards=ooda-observe:1|email-classifier:1|daily-briefer:1|ooda-act:1 trigger=no llm=no OODA_OK
```

All guards returned non-zero (nothing to do), so Beckett logged `OODA_OK` and
exited cleanly without invoking Claude.

## What You Get

Your role directory now has a valid **OODA.md** that Beckett can parse on every
cron run. The agenda is the contract between your role and the runner — change
it at any time to add, remove, or reorder the work your role performs.

## Further Reading

- [How Guards Decide Whether There's Work to Do](/beckett/2026/04/29/guards-smart-preflight-decisions.html) — understand what each skill slug maps to
- [Running Your Role's OODA Heartbeat](/beckett/2026/04/30/beckett-run-the-heartbeat-loop.html) — schedule Beckett as a cron job
