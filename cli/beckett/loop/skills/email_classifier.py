"""Email classifier skill — guard and agent."""

from __future__ import annotations

import subprocess

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
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

Your job is to classify unread inbox emails that have not yet been labeled by
the email-agent system. For each email:
1. Call get_unclassified_emails to get a list of unlabeled messages.
2. For each message, call get_email_body to read the full content.
3. Decide the correct label: reply_needed, review, todo, or summarize.
4. Call apply_gmail_label to apply the label.

Rules:
- reply_needed: email requires a personal response from you.
- review: FYI, newsletters, announcements — read but no action.
- todo: contains an actionable task you need to track.
- summarize: long thread or document to summarize later.
- Skip emails that are clearly automated noise or spam.

Return EmailClassificationResult with totals.
"""

_email_agent: Agent = build_skill_agent(
    system_prompt=_SYSTEM_PROMPT,
    output_type=EmailClassificationResult,
)


@_email_agent.tool
async def get_unclassified_emails(ctx: RunContext[RoleDeps]) -> str:
    """List inbox emails that have not yet received an email-agent label."""
    gws_acc = ctx.deps.env.get("GWS_PROFILE", ctx.deps.role)
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["gws", "gmail", "triage", "--account", gws_acc,
             "--filter", "-label:reply_needed -label:review -label:todo -label:summarize"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip() or "(no unclassified emails)"
    except Exception as exc:
        return f"(error: {exc})"


@_email_agent.tool
async def get_email_body(ctx: RunContext[RoleDeps], email_id: str) -> str:
    """Fetch the full body of an email by its message ID."""
    gws_acc = ctx.deps.env.get("GWS_PROFILE", ctx.deps.role)
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["gws", "gmail", "messages", "get", "--account", gws_acc,
             "--id", email_id, "--format", "full"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout.strip() or "(empty body)"
    except Exception as exc:
        return f"(error: {exc})"


@_email_agent.tool
async def apply_gmail_label(ctx: RunContext[RoleDeps], email_id: str, label: str) -> str:
    """Apply an email-agent label to a message. Only valid labels are accepted (Rule 3)."""
    if label not in VALID_EMAIL_LABELS:
        return f"rejected: '{label}' is not a valid email-agent label ({sorted(VALID_EMAIL_LABELS)})"
    gws_acc = ctx.deps.env.get("GWS_PROFILE", ctx.deps.role)
    timeout = int(ctx.deps.env.get("BECKETT_GUARD_TIMEOUT", "5"))
    try:
        proc = subprocess.run(
            ["gws", "gmail", "labels", "apply", "--account", gws_acc,
             "--id", email_id, "--label", label],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return "applied" if proc.returncode == 0 else f"error: {proc.stderr.strip()[:200]}"
    except Exception as exc:
        return f"(error: {exc})"


# ── Guard ─────────────────────────────────────────────────────────────────────


def _guard_timeout(deps: RoleDeps) -> int:
    try:
        return max(1, int(deps.env.get("BECKETT_GUARD_TIMEOUT") or deps.env.get("MASKS_GUARD_TIMEOUT") or 5))
    except (ValueError, TypeError):
        return 5


async def email_classifier_guard(deps: RoleDeps) -> GuardOutcome:
    """Trigger if there are unread emails in the inbox."""
    gws_acc = deps.env.get("GWS_PROFILE", deps.role)
    try:
        proc = subprocess.run(
            ["gws", "gmail", "triage", "--account", gws_acc],
            capture_output=True,
            text=True,
            timeout=_guard_timeout(deps),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = len([ln for ln in proc.stdout.splitlines() if ln.strip()])
            return GuardOutcome(triggered=True, detail=f"{lines} unread")
    except Exception:
        pass
    return GuardOutcome(triggered=False, detail="no unread")


# ── Agent ─────────────────────────────────────────────────────────────────────


async def email_classifier_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    """Run the email classifier agent.

    - When BECKETT_MODEL is set: Pydantic AI fetches each email and classifies it.
    - Fallback: calls invoke_claude with the signal detail as context.
    """
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
