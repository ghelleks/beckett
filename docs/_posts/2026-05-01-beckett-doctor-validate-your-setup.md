---
layout: post
title: "Catching Configuration Errors Before They Bite You with beckett doctor"
date: 2026-05-01
categories: [components]
excerpt: "In this post you will learn how to use beckett doctor to validate your OODA.md agendas and guard scripts before trusting your cron job to run them correctly."
---

## The Problem

You've created an **OODA.md**, added your skill slugs, and pointed Beckett at
your role directory. But if a guard file is misnamed, the wrong skills are
listed, or the agenda has a formatting error, Beckett will run silently and log
`OODA_OK` every cycle — not because there's nothing to do, but because the
guards it expected weren't there. You won't know something is wrong until you
notice Claude hasn't acted on anything in days.

## The Component

`beckett doctor` is the validation command. It inspects every role's
**OODA.md** and confirms that the agenda parses correctly and that every
referenced guard script exists and is executable. Run it after any change to
**OODA.md**, after installing Beckett on a new machine, or any time a cron run
seems suspiciously quiet.

## How It Works

- Collects role directories from `MASKS_BASE` (auto-detected from your
  environment or `~/Desktop/.env`), or from explicit paths you provide.
- **Check 1 — `ooda_agenda`:** Parses every role's **OODA.md**. Fails if a
  role's agenda yields zero skills (empty file, malformed sections, or no
  valid slugs).
- **Check 2 — `guards_executable`:** For every skill slug found across all
  roles, verifies that `guards/<slug>.sh` exists and is executable (`chmod
  +x`). Fails if any guard is missing or lacks execute permission.
- Prints `[PASS]` or `[FAIL]` for each check. Exits with code 1 if any check
  fails.
- `--json` outputs a machine-readable result for use in CI pipelines:
  `{"ok": true, "checks": [...]}`.

## Walkthrough

**1. Run doctor against a role directory.**

```bash
$ beckett doctor ~/Desktop/masks-base/work

[PASS] ooda_agenda: all roles parseable
[PASS] guards_executable: all guards present
```

Both checks pass — your configuration is valid.

**2. Introduce a deliberate agenda error and see it caught.**

Open **OODA.md** and add a malformed item (a bullet instead of a numbered
list entry):

```markdown
### Act

1. `ooda-act`
- this line is wrong
```

Run doctor again:

```bash
$ beckett doctor ~/Desktop/masks-base/work

[FAIL] ooda_agenda: missing or empty agenda: work
[PASS] guards_executable: all guards present
```

The agenda check fails because the parser warns on bullet-list lines in agenda
sections. Fix the line (make it numbered or remove it) and run again:

```bash
$ beckett doctor ~/Desktop/masks-base/work

[PASS] ooda_agenda: all roles parseable
[PASS] guards_executable: all guards present
```

**3. Introduce a missing guard and see it caught.**

Add a slug to **OODA.md** that has no corresponding guard:

```markdown
### Act

1. `ooda-act`
2. `my-custom-guard`
```

```bash
$ beckett doctor ~/Desktop/masks-base/work

[PASS] ooda_agenda: all roles parseable
[FAIL] guards_executable: missing my-custom-guard.sh
```

Either add the guard script at `guards/my-custom-guard.sh` and make it
executable, or remove the slug from **OODA.md**.

**4. Use JSON output in a CI check.**

```bash
$ beckett doctor --json ~/Desktop/masks-base/work

{
  "ok": true,
  "checks": [
    {"id": "ooda_agenda", "status": "pass", "message": "all roles parseable"},
    {"id": "guards_executable", "status": "pass", "message": "all guards present"}
  ]
}
```

Add `beckett doctor --json` as a step in your CI pipeline to catch
configuration drift before it reaches production.

**5. Run doctor across all roles at once.**

If you have multiple roles under `MASKS_BASE`, omit the path argument and
doctor scans all of them:

```bash
$ MASKS_BASE=~/Desktop/masks-base beckett doctor

[PASS] ooda_agenda: all roles parseable
[PASS] guards_executable: all guards present
```

## What You Get

You now have a fast, repeatable check that confirms your OODA configuration is
correct. Run `beckett doctor` after every change to **OODA.md** and you will
catch errors before your cron job does.

## Further Reading

- [Defining What Your Role Cares About with OODA.md](/beckett/2026/04/28/ooda-md-your-roles-agenda.html) — how to write a valid agenda
- [Monitoring Your Roles with beckett status](/beckett/2026/05/02/beckett-status-monitor-your-roles.html) — check that cron runs are healthy after setup
