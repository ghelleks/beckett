"""Act skill — guard and agent."""

from __future__ import annotations

import subprocess

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
from beckett.loop.skill_agent import build_skill_agent, run_agent
from beckett.loop.spec import GuardOutcome

# ── Output type ───────────────────────────────────────────────────────────────


class ActResult(BaseModel):
    executed: int = 0
    failed: int = 0
    task_ids: list[str] = []


# ── Pydantic AI agent ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the Beckett Act agent for a Pirandello role.

Your job is to execute actionable tasks tagged @agent or @decision in Todoist.

Workflow:
1. Call get_agent_tasks to find tasks labeled @agent.
2. Call get_decision_tasks to find @decision tasks with qualifying user instructions.
3. For each task, call get_task_comments to read the instruction.
4. Call run_claude_skill('task-executor', instruction) to execute the task.
   The task-executor skill has full MCP access to perform the work.
5. After execution, call add_task_comment with the [agent] result summary.
6. Call complete_todoist_task to close the task.

Rules:
- Only process tasks with non-empty instructions not prefixed with [agent].
- If execution fails, call add_task_comment with the error and do NOT complete the task.
- Return ActResult with executed, failed counts, and task IDs processed.
"""

_act_agent: Agent = build_skill_agent(
    system_prompt=_SYSTEM_PROMPT,
    output_type=ActResult,
)


@_act_agent.tool
async def get_agent_tasks(ctx: RunContext[RoleDeps]) -> str:
    """List Todoist tasks labeled @agent."""
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["td", "find-tasks", "--filter", "@agent"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip() or "(no @agent tasks)"
    except Exception as exc:
        return f"(error: {exc})"


@_act_agent.tool
async def get_decision_tasks(ctx: RunContext[RoleDeps]) -> str:
    """List Todoist tasks labeled @decision."""
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["td", "find-tasks", "--filter", "@decision"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip() or "(no @decision tasks)"
    except Exception as exc:
        return f"(error: {exc})"


@_act_agent.tool
async def get_task_comments(ctx: RunContext[RoleDeps], task_id: str) -> str:
    """Fetch all comments on a Todoist task by ID."""
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["td", "get-comments", "--task-id", task_id],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip() or "(no comments)"
    except Exception as exc:
        return f"(error: {exc})"


@_act_agent.tool
async def complete_todoist_task(ctx: RunContext[RoleDeps], task_id: str) -> str:
    """Close a Todoist task by ID. Irreversible — only call after successful execution."""
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["td", "complete", "--task-id", task_id],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return "completed" if proc.returncode == 0 else f"error: {proc.stderr.strip()[:200]}"
    except Exception as exc:
        return f"(error: {exc})"


@_act_agent.tool
async def add_task_comment(ctx: RunContext[RoleDeps], task_id: str, content: str) -> str:
    """Post a comment on a Todoist task (typically an [agent] result summary)."""
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["td", "add-comment", "--task-id", task_id, "--content", content],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return "posted" if proc.returncode == 0 else f"error: {proc.stderr.strip()[:200]}"
    except Exception as exc:
        return f"(error: {exc})"


# ── Guard ─────────────────────────────────────────────────────────────────────


def _guard_timeout(deps: RoleDeps) -> int:
    try:
        return max(1, int(deps.env.get("BECKETT_GUARD_TIMEOUT") or deps.env.get("MASKS_GUARD_TIMEOUT") or 5))
    except (ValueError, TypeError):
        return 5


async def act_guard(deps: RoleDeps) -> GuardOutcome:
    """Trigger if there are @agent or @decision tasks in Todoist."""
    try:
        proc = subprocess.run(
            ["td", "find-tasks", "--filter", "(today | overdue) & (@agent | @decision)"],
            capture_output=True,
            text=True,
            timeout=_guard_timeout(deps),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            count = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            return GuardOutcome(triggered=True, detail=f"{count} actionable tasks")
    except Exception:
        pass
    return GuardOutcome(triggered=False, detail="no actionable tasks")


# ── Agent ─────────────────────────────────────────────────────────────────────


async def act_agent(deps: RoleDeps, guard: GuardOutcome, context: dict | None = None) -> dict:
    """Run the act agent.

    - Pydantic AI orchestrates: fetch tasks → read comments → delegate execution
      via run_claude_skill → complete tasks + post comments.
    - Fallback (no model): calls invoke_claude with signal context.
    """
    phase_context = ""
    if context and context.get("_phase_triggers"):
        phase_context = f"\nPhase trigger context: {context['_phase_triggers']}"

    prompt = (
        f"Role: {deps.role}\n"
        f"Signal: {guard.detail}{phase_context}\n\n"
        "Execute all actionable @agent and @decision Todoist tasks for this role."
    )

    fallback: dict = {"executed": 0, "failed": 0, "task_ids": []}
    return await run_agent(_act_agent, prompt, deps, fallback_result=fallback)
