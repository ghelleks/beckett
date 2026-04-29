"""Email classifier skill — guard and agent."""

from __future__ import annotations

import subprocess

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
from beckett.loop.gws_util import guard_timeout, gws_env
from beckett.loop.skill_agent import VALID_EMAIL_LABELS, build_skill_agent, run_agent
from beckett.loop.spec import GuardOutcome

# ── Output type ───────────────────────────────────────────────────────────────


class EmailClassificationResult(BaseModel):
    classified: int = 0
    skipped: int = 0
    labels_applied: list[str] = []


# ── Pydantic AI agent ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the Beckett email classifier for a Pirandello role.

Classify unread inbox emails that have not yet been labeled by the email-agent system.

Steps:
1. Call get_unclassified_emails to get a list of unlabeled messages.
2. For each message, call get_email_body to read the full content.
3. Decide the correct label: reply_needed, review, todo, or summarize.
4. Call apply_gmail_label to apply the label.

Label guide:
- reply_needed: requires a personal response from you.
- review: FYI, newsletters, announcements — read but no action.
- todo: actionable task you need to track.
- summarize: long thread or document to summarize later.
- Skip clearly automated noise or spam.

Return EmailClassificationResult with totals.
"""

_email_agent: Agent = build_skill_agent(
    system_prompt=_SYSTEM_PROMPT,
    output_type=EmailClassificationResult,
)


@_email_agent.tool
async def get_unclassified_emails(ctx: RunContext[RoleDeps]) -> str:
    """List unread inbox emails for classification."""
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage"],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return proc.stdout.strip() or "(no emails)"
    except Exception as exc:
        return f"(error: {exc})"


@_email_agent.tool
async def get_email_body(ctx: RunContext[RoleDeps], email_id: str) -> str:
    """Fetch the full body of an email by its message ID."""
    import json
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    params = json.dumps({"id": email_id, "format": "full"})
    try:
        proc = subprocess.run(
            ["gws", "gmail", "messages", "get", "--params", params],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return proc.stdout.strip() or "(empty body)"
    except Exception as exc:
        return f"(error: {exc})"


@_email_agent.tool
async def apply_gmail_label(ctx: RunContext[RoleDeps], email_id: str, label: str) -> str:
    """Apply an email-agent label to a message. Only valid labels are accepted."""
    if label not in VALID_EMAIL_LABELS:
        return f"rejected: '{label}' is not a valid label ({sorted(VALID_EMAIL_LABELS)})"
    import json
    env = gws_env(ctx.deps)
    timeout = guard_timeout(ctx.deps)
    params = json.dumps({"id": email_id, "addLabelIds": [label]})
    try:
        proc = subprocess.run(
            ["gws", "gmail", "messages", "modify", "--params", params],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return "applied" if proc.returncode == 0 else f"error: {proc.stderr.strip()[:200]}"
    except Exception as exc:
        return f"(error: {exc})"


# ── Guard ─────────────────────────────────────────────────────────────────────


async def email_classifier_guard(deps: RoleDeps) -> GuardOutcome:
    """Trigger if there are unread emails in the inbox."""
    env = gws_env(deps)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "+triage"],
            capture_output=True, text=True, timeout=guard_timeout(deps), env=env,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            count = max(0, lines - 1)  # subtract header line
            if count > 0:
                return GuardOutcome(triggered=True, detail=f"{count} unread")
    except Exception:
        pass
    return GuardOutcome(triggered=False, detail="no unread")


# ── Agent ─────────────────────────────────────────────────────────────────────


async def email_classifier_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    phase_context = ""
    if context and context.get("_phase_triggers"):
        phase_context = f"\nPhase trigger context: {context['_phase_triggers']}"

    prompt = (
        f"Role: {deps.role}\n"
        f"Signal: {guard.detail}{phase_context}\n\n"
        "Classify unread inbox emails and apply the appropriate email-agent labels."
    )

    fallback: dict = {"classified": 0, "skipped": 0, "labels_applied": []}
    return await run_agent(_email_agent, prompt, deps, fallback_result=fallback)
