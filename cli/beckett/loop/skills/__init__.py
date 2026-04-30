"""Register built-in loop skills."""

from __future__ import annotations

from beckett.loop.registry import register_agent, register_guard
from beckett.loop.skills.act import act_agent, act_guard
from beckett.loop.skills.daily_briefer import daily_briefer_agent, daily_briefer_guard
from beckett.loop.skills.email_classifier import email_classifier_agent, email_classifier_guard
from beckett.loop.skills.observe import observe_agent, observe_guard
from beckett.loop.skills.observe_context_refresh import (
    observe_context_refresh_agent,
    observe_context_refresh_guard,
)
from beckett.loop.skills.observe_rss import observe_rss_agent, observe_rss_guard
from beckett.loop.skills.orient_decisions import orient_decisions_agent, orient_decisions_guard
from beckett.loop.skills.orient_email import orient_email_agent, orient_email_guard
from beckett.loop.skills.orient_hygiene import orient_hygiene_agent, orient_hygiene_guard
from beckett.loop.skills.orient_meeting_prep import (
    orient_meeting_prep_agent,
    orient_meeting_prep_guard,
)
from beckett.loop.skills.orient_post_meeting import (
    orient_post_meeting_agent,
    orient_post_meeting_guard,
)
from beckett.loop.skills.orient_reply_drafter import (
    orient_reply_drafter_agent,
    orient_reply_drafter_guard,
)
from beckett.loop.skills.orient_todo_forwarder import (
    orient_todo_forwarder_agent,
    orient_todo_forwarder_guard,
)
from beckett.loop.skills.orient_synthesis import orient_synthesis_agent, orient_synthesis_guard
from beckett.loop.skills.scheduled import (
    scheduled_desktop_archive_agent,
    scheduled_desktop_archive_guard,
    scheduled_efficiency_email_agent,
    scheduled_efficiency_email_guard,
    scheduled_efficiency_log_agent,
    scheduled_efficiency_log_guard,
    scheduled_staff_update_draft_agent,
    scheduled_staff_update_draft_guard,
)


def register_builtin_skills() -> None:
    # ── Legacy Pirandello ids (backward compatible) ────────────────────────
    register_guard("ooda-observe", observe_guard)
    register_agent("ooda-observe", observe_agent)

    register_guard("email-classifier", email_classifier_guard)
    register_agent("email-classifier", email_classifier_agent)

    register_guard("mask-ooda-orient-synthesis", orient_synthesis_guard)
    register_agent("mask-ooda-orient-synthesis", orient_synthesis_agent)

    register_guard("daily-briefer", daily_briefer_guard)
    register_agent("daily-briefer", daily_briefer_agent)

    register_guard("ooda-act", act_guard)
    register_agent("ooda-act", act_agent)

    # ── Beckett OODA ids ─────────────────────────────────────────────────────
    register_guard("beckett-observe", observe_guard)
    register_agent("beckett-observe", observe_agent)

    register_guard("beckett-observe-rss", observe_rss_guard)
    register_agent("beckett-observe-rss", observe_rss_agent)

    register_guard("beckett-observe-context-refresh", observe_context_refresh_guard)
    register_agent("beckett-observe-context-refresh", observe_context_refresh_agent)

    register_guard("beckett-orient-decisions", orient_decisions_guard)
    register_agent("beckett-orient-decisions", orient_decisions_agent)

    register_guard("beckett-orient-email", orient_email_guard)
    register_agent("beckett-orient-email", orient_email_agent)

    register_guard("beckett-orient-hygiene", orient_hygiene_guard)
    register_agent("beckett-orient-hygiene", orient_hygiene_agent)

    register_guard("beckett-orient-reply-drafter", orient_reply_drafter_guard)
    register_agent("beckett-orient-reply-drafter", orient_reply_drafter_agent)

    register_guard("beckett-orient-todo-forwarder", orient_todo_forwarder_guard)
    register_agent("beckett-orient-todo-forwarder", orient_todo_forwarder_agent)

    register_guard("beckett-orient-meeting-prep", orient_meeting_prep_guard)
    register_agent("beckett-orient-meeting-prep", orient_meeting_prep_agent)

    register_guard("beckett-orient-post-meeting", orient_post_meeting_guard)
    register_agent("beckett-orient-post-meeting", orient_post_meeting_agent)

    register_guard("beckett-act", act_guard)
    register_agent("beckett-act", act_agent)

    register_guard("beckett-scheduled-staff-update-draft", scheduled_staff_update_draft_guard)
    register_agent("beckett-scheduled-staff-update-draft", scheduled_staff_update_draft_agent)

    register_guard("beckett-scheduled-efficiency-log", scheduled_efficiency_log_guard)
    register_agent("beckett-scheduled-efficiency-log", scheduled_efficiency_log_agent)

    register_guard("beckett-scheduled-efficiency-email", scheduled_efficiency_email_guard)
    register_agent("beckett-scheduled-efficiency-email", scheduled_efficiency_email_agent)

    register_guard("beckett-scheduled-desktop-archive", scheduled_desktop_archive_guard)
    register_agent("beckett-scheduled-desktop-archive", scheduled_desktop_archive_agent)
