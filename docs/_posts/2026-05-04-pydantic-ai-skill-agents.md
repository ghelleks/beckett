---
layout: post
title: "Replacing Shell Subprocesses with Pydantic AI Skill Agents"
date: 2026-05-04
categories: [components]
excerpt: "In this post you will learn how Beckett's Pydantic AI skill agents work, how to configure a loop.yaml, and how agents share context and memory tools within each OODA phase."
---

## The Problem

The original Beckett runner invoked Claude once per cycle with only your
`OODA.md` file as context. Skills had no way to read from role memory, write
structured observations, or know what other skills in the same phase had
discovered. Each cycle was a single, context-thin subprocess call. If you
wanted a skill to check email and then write a structured note to memory, that
logic had to live entirely inside a shell guard or an unconstrained Claude
session.

## The Component

Beckett's loop runtime replaces the shell-subprocess runner with **Pydantic AI
skill agents** — one Python agent per skill, each with typed tools for memory
reads and writes and the ability to delegate complex multi-step work to Claude.
Skills share a common tool set via a factory function, receive typed role
context via `RoleDeps`, and run in a two-pass cycle that gives each agent
visibility into what its sibling guards detected.

## How It Works

- **`LoopSpec`** replaces `OODA.md` as the runtime configuration. You write
  a `loop.yaml` (or `loop.json` or `loop.py`) in the role directory with
  three sections — `observe`, `orient`, `act` — where each entry declares an
  `id`, an optional `guard` override, and an `agent` name.
- **`RoleDeps`** is a typed Pydantic model injected into every agent and tool.
  It carries the role directory, `MASKS_BASE`, merged environment, and the
  loaded `LoopSpec`.
- **`build_skill_agent`** is a factory that creates a `pydantic_ai.Agent`
  with four shared tools pre-registered:
  - `run_claude_skill` — delegates to `claude --print` for multi-step agentic
    work that needs MCP access or real-world side effects
  - `write_memory_file` — writes to `Memory/<subpath>.md` with path
    enforcement (writes stay inside the role memory directory)
  - `read_memory_file` — reads a memory file by relative subpath
  - `search_memory` — semantic search over role memory, returns up to 10
    results as JSON
- **Two-pass execution** happens per phase: pass 1 runs all guards and builds
  a trigger map; pass 2 runs agents for triggered entries in document order,
  with the full trigger map in context so each agent can see what else fired
  in its phase.
- **Model selection**: agents use the model named in `BECKETT_MODEL`. If that
  env var is absent but `BECKETT_LLM_CMD` is set, execution falls back to
  `invoke_claude` directly. If neither is set, the skill is skipped with a
  warning.
- Each cycle writes a structured result to
  `<role>/.ooda-state/last-run.json` containing per-phase, per-skill outcomes,
  guard trigger details, and whether a git commit was made.

## Walkthrough

**1. Create a `loop.yaml` in your role directory.**

```yaml
# ~/Desktop/masks-base/work/loop.yaml
observe:
  entries:
    - id: ooda-observe
      agent: observe

orient:
  entries:
    - id: email-classifier
      agent: email_classifier

act:
  entries:
    - id: daily-briefer
      agent: daily_briefer
    - id: ooda-act
      agent: act

active_hours: "09:00-17:00"
interval_minutes: 15
```

Each `agent` value references a registered skill agent (the five built-in
agents are `observe`, `email_classifier`, `daily_briefer`, `act`, and
`orient_synthesis`).

**2. Set your model environment variable.**

```bash
$ export BECKETT_MODEL="anthropic:claude-sonnet-4-6"
$ export ANTHROPIC_API_KEY="sk-ant-..."
```

Or use `BECKETT_LLM_CMD` to keep using the subprocess fallback:

```bash
$ export BECKETT_LLM_CMD="claude --print --output-format text"
```

**3. Validate your configuration.**

```bash
$ beckett doctor ~/Desktop/masks-base/work

[PASS] loop_spec: all roles parseable
[PASS] registry_coverage: all agents registered
[PASS] model_env: BECKETT_MODEL or LLM_CMD is set
```

**4. Run a dry run to check guard outcomes without invoking any agents.**

```bash
$ beckett loop --dry-run --role-target ~/Desktop/masks-base/work

PHASE      SKILL             GUARD
observe    ooda-observe      triggered=False  detail=no pending observations
orient     email-classifier  triggered=False  detail=inbox empty
act        daily-briefer     triggered=False  detail=outside active window
act        ooda-act          triggered=True   detail=1 @agent task due
```

One guard triggered — `ooda-act` found a task. The dry run shows this without
spending any tokens on agent invocations.

**5. Run the full loop cycle.**

```bash
$ beckett loop --once --role-target ~/Desktop/masks-base/work

work: triggered=1/4 success=yes committed=yes
```

One out of four skills triggered and ran its agent. A git commit was made
because the agent wrote a memory file.

**6. Inspect the run result.**

```bash
$ cat ~/Desktop/masks-base/work/.ooda-state/last-run.json
```

```json
{
  "role": "work",
  "started_at": "2026-05-04T09:15:01+00:00",
  "finished_at": "2026-05-04T09:15:08+00:00",
  "triggered_count": 1,
  "total_entries": 4,
  "success": true,
  "committed": true,
  "phases": [
    {
      "phase": "act",
      "skills": [
        {
          "id": "ooda-act",
          "guard": {"triggered": true, "detail": "1 @agent task due"},
          "agent_result": {"tasks_processed": 1}
        }
      ]
    }
  ]
}
```

**7. Run on a continuous interval (daemon mode).**

```bash
$ beckett loop --role-target ~/Desktop/masks-base/work --interval 15m
```

The daemon sleeps for 15 minutes between cycles and handles `SIGINT`/`SIGTERM`
cleanly. Active-hours enforcement happens inside each cycle — the daemon
continues running outside active hours and simply skips agent invocations.

## What You Get

Your role now runs typed, structured skill agents instead of a single
unconstrained Claude session. Each agent has read and write access to role
memory through enforced tool calls, can see what sibling guards detected in
the same phase, and produces a structured JSON result you can inspect and
monitor. Skills are testable in isolation using `beckett loop --skill <id>`.

## Further Reading

- [Sandboxing the Agent Loop with OpenShell](/beckett/2026/05/05/openshell-sandboxing.html) — restrict filesystem and network access for agent subprocesses
- [Catching Configuration Errors with beckett doctor](/beckett/2026/05/01/beckett-doctor-validate-your-setup.html) — validate loop.yaml and registry coverage before running
