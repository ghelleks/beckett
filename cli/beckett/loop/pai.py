"""Pydantic AI helper wrappers."""

from __future__ import annotations

from typing import Any

from beckett.loop.deps import RoleDeps


async def maybe_run_pydantic_agent(
    deps: RoleDeps,
    *,
    system_prompt: str,
    prompt: str,
) -> dict[str, Any] | None:
    """
    Run a lightweight Pydantic AI agent only when a model is configured.

    Returns None when no model is configured or if runtime invocation fails.
    """
    model = deps.env.get("BECKETT_MODEL", "").strip()
    if not model:
        return None
    try:
        from pydantic_ai import Agent
    except Exception:
        return None
    try:
        agent = Agent(model, deps_type=RoleDeps, output_type=dict, system_prompt=system_prompt)
        result = await agent.run(prompt, deps=deps)
        return result.output if hasattr(result, "output") else None
    except Exception:
        return None
