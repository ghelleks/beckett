"""Guard/agent registries for loop runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from beckett.loop.spec import GuardOutcome

GuardFn = Callable[..., Awaitable[GuardOutcome]]
AgentFn = Callable[..., Awaitable[Any]]

_GUARDS: dict[str, GuardFn] = {}
_AGENTS: dict[str, AgentFn] = {}


def register_guard(name: str, fn: GuardFn) -> None:
    _GUARDS[name] = fn


def register_agent(name: str, fn: AgentFn) -> None:
    _AGENTS[name] = fn


def guard_for(name: str) -> GuardFn:
    if name not in _GUARDS:
        raise KeyError(f"guard not registered: {name}")
    return _GUARDS[name]


def agent_for(name: str) -> AgentFn:
    if name not in _AGENTS:
        raise KeyError(f"agent not registered: {name}")
    return _AGENTS[name]


def has_guard(name: str) -> bool:
    return name in _GUARDS


def has_agent(name: str) -> bool:
    return name in _AGENTS


def all_guard_ids() -> list[str]:
    return sorted(_GUARDS.keys())


def all_agent_ids() -> list[str]:
    return sorted(_AGENTS.keys())
