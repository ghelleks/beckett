---
layout: post
title: "Knowing Your System Is Working with beckett status"
date: 2026-05-02
categories: [components]
excerpt: "In this post you will learn how to use beckett status to confirm that your cron jobs are running and to spot roles that have gone stale or stopped logging."
---

## The Problem

Cron jobs run silently. After setting up Beckett to run every 15 minutes, you
have no easy way to verify that it's actually executing. If the cron daemon
restarts, the role directory moves, or a guard starts hanging, Beckett stops
doing anything useful — and you won't notice until work piles up unprocessed.
You need a quick way to see the health of all your roles at a glance.

## The Component

`beckett status` reads the `.ooda.log` file in each role directory and
summarizes it in a single-line table. For each role you see when it last ran
cleanly (no work found) and what the most recent log entry was. Run it any
time you want to confirm your cron jobs are alive and doing the right thing.

## How It Works

- Collects role directories from `MASKS_BASE` (or explicit paths you provide).
- For each role, reads `<role_dir>/.ooda.log` and:
  - **LAST_OODA_OK:** Scans the log from the bottom for the most recent line
    containing `OODA_OK` — the timestamp of the last clean "nothing to do"
    exit.
  - **LAST_LOG_LINE:** Returns the absolute last line in the log, regardless of
    type — useful for spotting errors, LLM invocations, or guard timeouts.
- If no log file exists, both columns show `never`.
- Output is a fixed-width table so you can scan across multiple roles quickly.

## Walkthrough

**1. Run status after your cron job has been running for a while.**

```bash
$ MASKS_BASE=~/Desktop/masks-base beckett status

ROLE             LAST_OODA_OK                               LAST_LOG_LINE
work             ts=2026-05-02T09:30:02-07:00 role=work ... ts=2026-05-02T09:45:01-07:00 role=work ...
personal         ts=2026-05-02T08:45:00-07:00 role=perso... ts=2026-05-02T09:00:03-07:00 role=perso...
```

Recent timestamps on both columns mean the cron job is running and no LLM
calls have been triggered since the last `OODA_OK`.

**2. Spot a role that has never run.**

If you recently added a role and haven't scheduled its cron entry yet, its log
will be absent:

```bash
$ beckett status ~/Desktop/masks-base/research

ROLE             LAST_OODA_OK                               LAST_LOG_LINE
research         never                                      never
```

`never` on both columns means the role directory has no `.ooda.log` at all.
Add the cron entry for this role and check again after the first run.

**3. Spot a role whose last activity was an LLM invocation.**

If the last log line is not `OODA_OK` but shows `trigger=yes llm=yes`, the
most recent cycle found work and invoked Claude:

```bash
$ beckett status ~/Desktop/masks-base/work

ROLE             LAST_OODA_OK                               LAST_LOG_LINE
work             ts=2026-05-02T09:30:02-07:00 role=work ... ts=2026-05-02T09:45:01-07:00 role=work guards=... trigger=yes llm=yes
```

This is normal — the role is healthy. `LAST_OODA_OK` still shows the prior
clean run.

**4. Spot a stale role.**

If `LAST_OODA_OK` shows a timestamp from yesterday (or earlier), the cron job
may have stopped:

```bash
$ beckett status ~/Desktop/masks-base/work

ROLE             LAST_OODA_OK                               LAST_LOG_LINE
work             ts=2026-05-01T17:00:01-07:00 role=work ... ts=2026-05-01T17:00:01-07:00 role=work ...
```

Check that the cron daemon is running and that the cron entry references the
correct path. Then manually run `beckett run <path>` once to confirm it works:

```bash
$ beckett run ~/Desktop/masks-base/work
$ beckett status ~/Desktop/masks-base/work

ROLE             LAST_OODA_OK                               LAST_LOG_LINE
work             ts=2026-05-02T10:01:03-07:00 role=work ... ts=2026-05-02T10:01:03-07:00 role=work ...
```

The timestamp is now current, confirming the problem was with cron rather than
Beckett itself.

**5. Check all roles in one command.**

With `MASKS_BASE` set, run status with no arguments to see every role:

```bash
$ MASKS_BASE=~/Desktop/masks-base beckett status

ROLE             LAST_OODA_OK                               LAST_LOG_LINE
personal         ts=2026-05-02T09:00:03-07:00 ...           ts=2026-05-02T09:00:03-07:00 ...
research         never                                      never
work             ts=2026-05-02T09:45:01-07:00 ...           ts=2026-05-02T09:45:01-07:00 ...
```

## What You Get

You now have a single command that tells you whether your autonomous roles are
alive and when they last did something. `beckett status` takes seconds to run
and replaces manually tailing log files across multiple directories.

## Further Reading

- [Running Your Role's OODA Heartbeat](/beckett/2026/04/30/beckett-run-the-heartbeat-loop.html) — how to schedule Beckett as a cron job
- [Catching Configuration Errors with beckett doctor](/beckett/2026/05/01/beckett-doctor-validate-your-setup.html) — validate your setup if status shows unexpected results
