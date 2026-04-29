"""Shared Pydantic AI agent factory and common tools for Beckett skill agents."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
from beckett.loop.memory_tools import (
    read_memory_file as _mem_read,
)
from beckett.loop.memory_tools import (
    search_memory as _mem_search,
)
from beckett.loop.memory_tools import (
    write_memory,
)

log = logging.getLogger(__name__)

# Valid email-agent label values — enforced in apply_gmail_label tool (Rule 3).
VALID_EMAIL_LABELS = frozenset({"reply_needed", "review", "todo", "summarize"})


def build_skill_agent(
    system_prompt: str,
    output_type: type,
    extra_tools: list | None = None,
) -> Agent:
    """Create a Pydantic AI Agent with shared Beckett tools pre-registered.

    The returned agent has no model bound at construction time. Pass the model
    string (e.g. "openai:gpt-4o") to agent.run(prompt, model=..., deps=deps).

    Shared tools follow the decision rules:
    - run_claude_skill  → Rule 5/6 (multi-step agentic delegation)
    - write_memory_file → Rule 3 (invariant-enforced write)
    - read_memory_file  → Rule 4 (deterministic file read)
    - search_memory     → Rule 4 (deterministic semantic search)
    """
    agent: Agent = Agent(
        deps_type=RoleDeps,
        output_type=output_type,
        system_prompt=system_prompt,
    )

    @agent.tool
    async def run_claude_skill(ctx: RunContext[RoleDeps], skill_name: str, prompt: str) -> str:
        """Delegate to Claude Code via subprocess. Use for multi-step agentic work
        requiring MCP access, browsing, or complex real-world side effects."""
        from beckett.loop.claude import invoke_claude  # lazy import avoids circular dep

        full_prompt = f"[skill: {skill_name}]\n{prompt}"
        return invoke_claude(ctx.deps, full_prompt)

    @agent.tool
    async def write_memory_file(ctx: RunContext[RoleDeps], subpath: str, content: str) -> str:
        """Write content to a role Memory file. subpath is relative to Memory/
        (e.g. 'Observations/note'). Path must stay within the role Memory directory."""
        path = write_memory(ctx.deps, subpath, content)
        return str(path)

    @agent.tool
    async def read_memory_file(ctx: RunContext[RoleDeps], subpath: str) -> str:
        """Read a role Memory file by relative subpath. Returns empty string if not found."""
        return _mem_read(ctx.deps, subpath) or ""

    @agent.tool
    async def search_memory(ctx: RunContext[RoleDeps], query: str) -> str:
        """Semantic search over role memory. Returns a JSON list of up to 10 matching entries."""
        results = _mem_search(ctx.deps, query)
        return json.dumps(results[:10])

    if extra_tools:
        for tool_fn in extra_tools:
            agent.tool(tool_fn)

    return agent


async def run_agent(
    agent: Agent,
    prompt: str,
    deps: RoleDeps,
    *,
    fallback_result: dict[str, Any],
) -> dict[str, Any]:
    """Run a Pydantic AI agent with BECKETT_MODEL from deps.env.

    When BECKETT_MODEL is not set:
    - If BECKETT_LLM_CMD or MASKS_LLM_CMD is configured, falls back to a direct
      invoke_claude call so the subprocess path is still exercised (useful for
      functional tests and for setups that prefer the subprocess delegation model).
    - Otherwise logs a warning and returns fallback_result.

    This fallback preserves testability: tests can set BECKETT_LLM_CMD to a stub
    without needing a real API key or Pydantic AI model mock.
    """
    model = deps.env.get("BECKETT_MODEL", "").strip()
    if model:
        try:
            result = await agent.run(prompt, deps=deps, model=model)
            out = result.output
            if isinstance(out, BaseModel):
                return out.model_dump(mode="json")
            return dict(out) if isinstance(out, dict) else {"result": str(out)}
        except Exception as exc:
            log.error("Pydantic AI agent failed for role=%s: %s", deps.role, exc)
            return {**fallback_result, "error": str(exc)}

    # No Pydantic AI model — try the subprocess fallback path
    llm_cmd = deps.env.get("BECKETT_LLM_CMD", "").strip() or deps.env.get(
        "MASKS_LLM_CMD", ""
    ).strip()
    if llm_cmd:
        from beckett.loop.claude import invoke_claude

        try:
            invoke_claude(deps, prompt)
        except Exception as exc:
            log.warning("invoke_claude fallback failed for role=%s: %s", deps.role, exc)
        return fallback_result

    log.warning(
        "Neither BECKETT_MODEL nor BECKETT_LLM_CMD set for role=%s; agent skipped",
        deps.role,
    )
    return fallback_result
