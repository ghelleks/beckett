---
layout: post
title: "Finding Cross-Role Patterns with Orient Synthesis"
date: 2026-05-03
categories: [components]
excerpt: "In this post you will learn how to configure the mask-ooda-orient-synthesis skill to scan Memory files across all your roles and surface patterns that span multiple contexts."
---

## The Problem

You keep separate notes for work, personal life, health, and creative
projects — each in its own Role directory with its own Memory folder. Themes
recur across all of them: a recurring feeling of overcommitment, a pattern in
how you respond to uncertainty, habits that show up in both professional and
personal contexts. But you never see the connection because the notes live in
separate directories and no single role has visibility into the others.

## The Component

`mask-ooda-orient-synthesis` is an Orient skill that runs once a week in your
`personal` role. It reads Memory files from every role under `MASKS_BASE`,
identifies patterns that appear in at least two distinct roles, and writes
structured synthesis documents to `personal/Memory/Synthesis/`. A guard script
enforces the weekly cadence and prevents redundant runs.

## How It Works

- The **guard** (`guards/mask-ooda-orient-synthesis.sh`) exits 0 only when:
  - Today is the configured synthesis day (default: Sunday, `SYNTHESIS_DAY=0`).
  - At least 7 days have passed since the last synthesis run (checked via
    `personal/.synthesis.log`).
- When triggered, the LLM receives your `personal/OODA.md` as context, which
  contains the skill specification for how to scan and synthesize.
- The skill scans `BASE/<role>/Memory/**/*.md` for every role that has a
  `ROLE.md` marker file. It excludes `personal/Memory/Synthesis/` itself from
  raw evidence mining.
- Session dates are inferred from YAML front matter, body keywords, or `git
  log`.
- A pattern is written to a synthesis file only if it appears in **two or more
  distinct roles** (`R ≥ 2`). Patterns from a single role are noted in the run
  summary as candidates, not written to disk.
- Each synthesis file at `personal/Memory/Synthesis/<kebab-name>.md` follows a
  fixed template: `First observed`, `Last updated`, `Status`, a neutral
  `Pattern` paragraph, and `Evidence` bullets.
- Patterns not refreshed in 90 days are marked `**Status:** stale` but not
  deleted.
- On completion, one line is appended to `personal/.synthesis.log`:
  `SYNTHESIS <ISO-8601 UTC> — <N> patterns found, <M> updated`.

## Walkthrough

**1. Add the synthesis skill to your personal role's OODA.md.**

Open `~/Desktop/masks-base/personal/OODA.md` and add the skill under
`### Orient`:

```markdown
### Orient

1. `mask-ooda-orient-synthesis`
```

**2. Validate the configuration.**

```bash
$ beckett doctor ~/Desktop/masks-base/personal

[PASS] ooda_agenda: all roles parseable
[PASS] guards_executable: all guards present
```

**3. Confirm the guard respects the day and cooldown.**

Run the guard directly on a day that is not Sunday (assuming today is a
weekday):

```bash
$ export BASE=~/Desktop/masks-base
$ export MASKS_BASE=~/Desktop/masks-base
$ guards/mask-ooda-orient-synthesis.sh; echo "exit: $?"

exit: 1
```

Exit 1 — not synthesis day. The LLM will not be invoked.

**4. Trigger synthesis manually for testing.**

Set `SYNTHESIS_DAY` to today's day-of-week number (0=Sunday, 1=Monday,
..., 6=Saturday) and remove any existing synthesis log:

```bash
$ export SYNTHESIS_DAY=$(date +%w)
$ rm -f ~/Desktop/masks-base/personal/.synthesis.log
$ guards/mask-ooda-orient-synthesis.sh; echo "exit: $?"

exit: 0
```

Exit 0 — the guard passes. Now run the full cycle:

```bash
$ beckett run ~/Desktop/masks-base/personal
```

**5. Inspect the synthesis output.**

After the run completes, check for new files in
`personal/Memory/Synthesis/`:

```bash
$ ls ~/Desktop/masks-base/personal/Memory/Synthesis/

recurring-overcommitment.md   decision-avoidance.md
```

Open one to review the structure:

```bash
$ cat ~/Desktop/masks-base/personal/Memory/Synthesis/recurring-overcommitment.md
```

```markdown
# Recurring Overcommitment

**First observed:** 2026-01-15
**Last updated:** 2026-05-03
**Status:** current

## Pattern

A pattern of accepting more responsibilities than available capacity allows,
visible across both professional project planning and personal scheduling.

## Evidence

- (work) 2026-02-10 — `Memory/2026-02-10-q1-retrospective.md` — noted three
  projects added without removing existing commitments
- (personal) 2026-03-22 — `Memory/2026-03-22-weekly-review.md` — identified
  weekend obligations expanding to fill available time
- (work) 2026-04-05 — `Memory/2026-04-05-sprint-planning.md` — team capacity
  estimate ignored in favour of stakeholder deadline
```

**6. Check the synthesis log.**

```bash
$ cat ~/Desktop/masks-base/personal/.synthesis.log

SYNTHESIS 2026-05-03T16:42:07+00:00 — 2 patterns found, 0 updated
```

## What You Get

Your personal role now runs a weekly synthesis pass that reads across all your
roles and surfaces the patterns that span your whole life — not just individual
contexts. Synthesis files accumulate over time, gaining evidence and marking
stale patterns that haven't recurred, giving you a long-running record of your
cross-role behavior.

## Further Reading

- [How Guards Decide Whether There's Work to Do](/beckett/2026/04/29/guards-smart-preflight-decisions.html) — understand the guard contract the synthesis guard follows
- [Running Your Role's OODA Heartbeat](/beckett/2026/04/30/beckett-run-the-heartbeat-loop.html) — how `beckett run` invokes the synthesis cycle
