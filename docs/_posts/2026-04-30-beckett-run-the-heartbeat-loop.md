---
layout: post
title: "Running Your Role's OODA Heartbeat"
date: 2026-04-30
categories: [components]
excerpt: "In this post you will learn how to run beckett run manually, read its log output, and schedule it as a cron job so your role operates autonomously."
---

## The Problem

You have a Role directory set up with an `OODA.md` agenda and guard scripts
wired to real signals. But who runs the cycle? Manual invocation doesn't
scale — you want your roles to evaluate themselves every 15 minutes, act when
there's work, and stay silent when there isn't, without you touching a
keyboard.

## The Component

`beckett run <path>` is the main command. It orchestrates the full OODA loop
for one role: reads the agenda, merges environment, runs every guard, and
invokes Claude with your **OODA.md** as context if any guard finds work. Every
invocation — productive or not — appends a structured line to `.ooda.log`.
Schedule it with cron and your role runs itself.

## How It Works

- **Resolve the role directory.** You can pass an absolute path, a
  `~`-prefixed path, a path relative to the current directory, or a bare name
  that resolves to `MASKS_BASE/<name>`.
- **Merge environment.** Beckett reads `parent/.env` first, then
  `role_dir/.env` (role wins on conflicts). This gives you centralized config
  in the base directory and per-role overrides.
- **Parse OODA.md.** The `### Observe`, `### Orient`, and `### Act` sections
  are scanned for skill slugs. They run in document order.
- **Run all guards.** Each `guards/<slug>.sh` executes with a 5-second
  timeout. All guards run — there is no early exit.
- **Decide whether to invoke Claude.** If any guard exits 0: Beckett spawns
  the LLM command with the full text of **OODA.md** piped to stdin. No other
  files are passed — Memory, Reference, and Index are not included in the
  heartbeat context.
- **Log the result.** One structured line is always written to
  `<role_dir>/.ooda.log`: timestamp, role name, guard exit codes, trigger
  status, and whether Claude was spawned.

The default LLM command is `claude --print --output-format text`. Override it
by setting `BECKETT_LLM_CMD` in your `.env`.

## Walkthrough

**1. Install Beckett.**

```bash
$ uv tool install /path/to/beckett/cli
```

Confirm it's on your path:

```bash
$ beckett --version

beckett 0.1.0
```

**2. Run the command manually against your role directory.**

```bash
$ beckett run ~/Desktop/masks-base/work
```

Beckett exits silently on success. Check the log:

```bash
$ tail -1 ~/Desktop/masks-base/work/.ooda.log

ts=2026-04-30T09:00:02-07:00 role=work guards=ooda-observe:1|email-classifier:1|daily-briefer:1|ooda-act:1 trigger=no llm=no OODA_OK
```

`OODA_OK` means every guard returned non-zero — no work was found, no LLM was
invoked.

**3. Trigger a real run with work present.**

Tag a Todoist task `@agent` with today's due date, then run again:

```bash
$ beckett run ~/Desktop/masks-base/work
$ tail -1 ~/Desktop/masks-base/work/.ooda.log

ts=2026-04-30T09:02:15-07:00 role=work guards=ooda-observe:1|email-classifier:1|daily-briefer:1|ooda-act:0 trigger=yes llm=yes
```

`ooda-act:0` means that guard found work. `trigger=yes llm=yes` confirms
Claude was invoked.

**4. Add the cron entry.**

Open your crontab:

```bash
$ crontab -e
```

Add one line per role you want to run automatically:

```text
*/15 * * * 1-5 beckett run /Users/you/Desktop/masks-base/work 2>>/Users/you/Desktop/masks-base/work/.ooda.log
```

This runs every 15 minutes on weekdays. Use an absolute path to the role
directory — `MASKS_BASE` may not be set in the cron environment.

**5. Verify the cron job is running.**

Wait for the next 15-minute boundary, then check the log:

```bash
$ tail -3 ~/Desktop/masks-base/work/.ooda.log

ts=2026-04-30T09:00:02-07:00 role=work guards=ooda-observe:1|email-classifier:1|daily-briefer:1|ooda-act:1 trigger=no llm=no OODA_OK
ts=2026-04-30T09:15:01-07:00 role=work guards=ooda-observe:1|email-classifier:1|daily-briefer:1|ooda-act:1 trigger=no llm=no OODA_OK
ts=2026-04-30T09:30:02-07:00 role=work guards=ooda-observe:1|email-classifier:1|daily-briefer:1|ooda-act:1 trigger=no llm=no OODA_OK
```

Regular `OODA_OK` lines mean the cron job is running and the role is healthy.

## What You Get

Your role now runs autonomously on a schedule. Beckett evaluates every signal
in your agenda on each cycle, calls Claude only when something needs attention,
and leaves a structured audit trail in `.ooda.log`. You don't need to check in
— the log tells you everything.

## Further Reading

- [Catching Configuration Errors with beckett doctor](/beckett/2026/05/01/beckett-doctor-validate-your-setup.html) — validate your setup before relying on cron
- [Monitoring Your Roles with beckett status](/beckett/2026/05/02/beckett-status-monitor-your-roles.html) — check that cron is actually running
