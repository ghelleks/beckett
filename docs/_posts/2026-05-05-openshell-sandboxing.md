---
layout: post
title: "Sandboxing the Agent Loop with OpenShell"
date: 2026-05-05
categories: [components]
excerpt: "In this post you will learn how to use OpenShell to confine Beckett's LLM subprocesses to specific filesystem paths and network destinations, preventing unintended access during autonomous background runs."
---

## The Problem

When `beckett loop` runs autonomously in the background, it invokes
subprocesses — `claude --print`, `gws`, `td` — with the same operating system
permissions as your user account. Those processes can read any file you can
read, write anywhere you can write, and make any network call your machine
allows. For background automation that runs while you're not watching, that's
a broad surface area. A misconfigured skill, an unexpected model output, or a
dependency bug could read files outside the role directory or make network
calls you didn't intend.

## The Component

Beckett supports optional **OpenShell sandboxing**. When you set the
`BECKETT_OPENSHELL_POLICY` environment variable to a policy file, every LLM
subprocess call is wrapped in `openshell run --policy <file>`, which enforces
filesystem and network access rules via a container runtime (Docker or Podman).
A ready-to-use policy template is included in the Beckett distribution at
`beckett-agent.yaml.example`.

## How It Works

- When `BECKETT_OPENSHELL_POLICY` is set, `invoke_claude` prepends
  `openshell run --policy <policy_file> --` to the subprocess command instead
  of calling it directly. The LLM binary runs inside the sandbox.
- The policy file has two sections:
  - **`filesystem_policy`** declares `read_only` and `read_write` path lists.
    The bundled template grants read-only access to the full role directory and
    read-write access only to `Memory/`, `.ooda-state/`, and `.ooda-pending/`.
  - **`network_policies`** grants per-binary network access by destination
    host and port. The template allows `claude` to reach `api.anthropic.com`,
    `gws` to reach Google Workspace APIs, and `td` to reach `api.todoist.com`.
    All other network traffic from agent subprocesses is blocked.
- OpenShell requires **Docker Engine 28.04+** or **Podman** (configure
  `CONTAINER_HOST` to the socket path, or let OpenShell auto-detect on macOS
  via `podman machine inspect`).
- `beckett doctor` includes an `openshell` check. It verifies that the
  `openshell` binary is on `PATH`, the policy file exists, and the container
  daemon is reachable. This check emits `[WARN]` rather than `[FAIL]` —
  sandboxing is strongly recommended but not required to run the loop.

## Walkthrough

**1. Install OpenShell.**

Follow the [OpenShell installation guide](https://github.com/NVIDIA/OpenShell)
for your platform. Confirm it's available:

```bash
$ openshell --version

OpenShell 1.2.0
```

**2. Confirm your container runtime is running.**

```bash
$ docker info --format '{{.ServerVersion}}'

28.0.4
```

Or for Podman:

```bash
$ podman machine inspect --format '{{.State}}'

running
```

**3. Copy the policy template and substitute your role directory.**

```bash
$ cp "$(python3 -c 'import beckett; print(beckett.__file__.replace("__init__.py",""))')_data/beckett-agent.yaml.example" \
    ~/Desktop/masks-base/work/beckett-agent.yaml
```

Open the file and replace `{role_dir}` with your absolute role path, or use
`envsubst`:

```bash
$ export ROLE_DIR=~/Desktop/masks-base/work
$ envsubst < ~/Desktop/masks-base/work/beckett-agent.yaml > /tmp/beckett-agent-resolved.yaml
$ mv /tmp/beckett-agent-resolved.yaml ~/Desktop/masks-base/work/beckett-agent.yaml
```

**4. Set the policy environment variable.**

Add this to your role's `.env` file so Beckett picks it up on every cycle:

```bash
BECKETT_OPENSHELL_POLICY=/Users/you/Desktop/masks-base/work/beckett-agent.yaml
```

Or export it in the current shell for testing:

```bash
$ export BECKETT_OPENSHELL_POLICY=~/Desktop/masks-base/work/beckett-agent.yaml
```

**5. Run `beckett doctor` to verify the sandbox is ready.**

```bash
$ beckett doctor ~/Desktop/masks-base/work

[PASS] loop_spec: all roles parseable
[PASS] registry_coverage: all agents registered
[PASS] model_env: BECKETT_MODEL or LLM_CMD is set
[PASS] openshell: openshell ready, policy=/Users/you/Desktop/masks-base/work/beckett-agent.yaml
```

If the container daemon is not running, doctor reports a warning:

```bash
[WARN] openshell: openshell daemon not reachable (is Docker/Podman running?)
```

Start Docker or Podman and re-run doctor before continuing.

**6. Run a dry run to confirm the sandbox doesn't block guard evaluation.**

Guards run as Python functions inside Beckett itself, not as subprocesses, so
they are not affected by the sandbox. The dry run verifies your `loop.yaml` is
valid and guards can evaluate:

```bash
$ beckett loop --dry-run --role-target ~/Desktop/masks-base/work

PHASE      SKILL             GUARD
observe    ooda-observe      triggered=False  detail=no pending observations
orient     email-classifier  triggered=False  detail=inbox empty
act        daily-briefer     triggered=False  detail=outside active window
act        ooda-act          triggered=False  detail=no tasks due
```

**7. Trigger an agent and confirm sandbox enforcement.**

Force-trigger a skill to invoke the sandbox:

```bash
$ beckett loop --skill ooda-observe --force --role-target ~/Desktop/masks-base/work

work[ooda-observe]: triggered=yes(forced) success=yes committed=no
```

If the skill tries to write outside `Memory/`, `.ooda-state/`, or
`.ooda-pending/`, OpenShell will block the write and the agent will report an
error. Review `.ooda-state/last-run.json` to inspect the outcome.

**8. Add custom network permissions if your skills need them.**

Uncomment and edit the `allow_custom` block in your policy file:

```yaml
allow_custom:
  binaries: ["curl"]
  destinations:
    - host: "api.example.com"
      port: 443
```

Re-run `beckett doctor` after any policy change to confirm the daemon accepts
the updated file.

## What You Get

Your agent subprocesses now run inside a container with explicit allowlists for
filesystem access and network destinations. Legitimate skill behavior (reading
the role directory, writing to Memory, calling the Anthropic API) is
unaffected. Any access outside those bounds is blocked at the OS level, not
just by convention. The sandbox is transparent to your existing `loop.yaml`
configuration — no skill code changes are needed.

## Further Reading

- [Replacing Shell Subprocesses with Pydantic AI Skill Agents](/beckett/2026/05/04/pydantic-ai-skill-agents.html) — how the agent loop that OpenShell wraps is structured
- [Catching Configuration Errors with beckett doctor](/beckett/2026/05/01/beckett-doctor-validate-your-setup.html) — the full list of checks doctor performs, including the openshell check
