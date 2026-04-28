"""Register built-in loop skills."""

from __future__ import annotations

from beckett.loop.registry import register_agent, register_guard
from beckett.loop.skills.act import act_agent, act_guard
from beckett.loop.skills.daily_briefer import daily_briefer_agent, daily_briefer_guard
from beckett.loop.skills.email_classifier import email_classifier_agent, email_classifier_guard
from beckett.loop.skills.observe import observe_agent, observe_guard
from beckett.loop.skills.orient_synthesis import orient_synthesis_agent, orient_synthesis_guard


def register_builtin_skills() -> None:
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
