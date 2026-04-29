"""Orient synthesis skill — guard and agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from beckett.loop.deps import RoleDeps
from beckett.loop.memory_tools import write_memory
from beckett.loop.skill_agent import build_skill_agent, run_agent
from beckett.loop.spec import GuardOutcome

# ── Output type ───────────────────────────────────────────────────────────────


class SynthesisResult(BaseModel):
    patterns_found: int = 0
    written: int = 0
    stale_updated: int = 0


# ── Pydantic AI agent ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the Beckett orient synthesis agent for a Pirandello role.

Your job is to synthesize cross-role memory patterns by reading recent observation
files across all roles and identifying recurring themes worth persisting.

Steps:
1. Call list_role_memory_files for the 'personal' role and for each other role
   you can discover.
2. Call read_memory_file to read the content of recent observation files.
3. Identify patterns: recurring topics, unresolved tensions, emerging priorities.
4. For each significant pattern, call write_synthesis to create or update a
   Synthesis/ entry in personal Memory.
5. Mark stale synthesis entries (status: stale → status: current) when updated.
6. Return SynthesisResult with patterns_found, written, stale_updated counts.
"""

_synthesis_agent: Agent = build_skill_agent(
    system_prompt=_SYSTEM_PROMPT,
    output_type=SynthesisResult,
)


@_synthesis_agent.tool
async def list_role_memory_files(
    ctx: RunContext[RoleDeps], role: str = "current", subdir: str = "Observations"
) -> str:
    """List Memory/<subdir>/ files for a role. role='current' means this role;
    use role='personal' for the personal role, or any other role name."""
    deps = ctx.deps
    if role == "current":
        base = deps.role_dir
    elif role == "personal":
        base = deps.personal_dir
    else:
        base = deps.masks_base / role
    memory_subdir = base / "Memory" / subdir
    if not memory_subdir.is_dir():
        return f"(no {subdir}/ directory found for role={role})"
    files = sorted(memory_subdir.glob("*.md"))
    if not files:
        return f"(no .md files in {subdir}/ for role={role})"
    return "\n".join(str(f.relative_to(base / "Memory")) for f in files[:50])


@_synthesis_agent.tool
async def read_role_memory_file(
    ctx: RunContext[RoleDeps], subpath: str, role: str = "current"
) -> str:
    """Read a Memory file for the specified role. subpath is relative to Memory/.
    role='current', 'personal', or a role name."""
    deps = ctx.deps
    if role == "current":
        base = deps.role_dir
    elif role == "personal":
        base = deps.personal_dir
    else:
        base = deps.masks_base / role
    rel = Path(subpath)
    if rel.suffix != ".md":
        rel = rel.with_suffix(".md")
    target = (base / "Memory" / rel).resolve()
    if not target.is_file():
        return "(file not found)"
    return target.read_text(encoding="utf-8", errors="replace")


@_synthesis_agent.tool
async def write_synthesis(ctx: RunContext[RoleDeps], subpath: str, content: str) -> str:
    """Write a Synthesis/ entry to personal Memory. subpath must start with 'Synthesis/'.
    Only usable when this agent is running for the personal role."""
    if not subpath.startswith("Synthesis/"):
        return "rejected: subpath must start with 'Synthesis/'"
    try:
        path = write_memory(ctx.deps, subpath, content, allow_personal_synthesis=True)
        return str(path)
    except Exception as exc:
        return f"error: {exc}"


# ── Guard helpers ─────────────────────────────────────────────────────────────


def _recent_synthesis(log_path: Path, cutoff: datetime) -> bool:
    if not log_path.is_file():
        return False
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("SYNTHESIS "):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        raw = parts[1].replace("Z", "+00:00")
        try:
            ts = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts > cutoff:
            return True
    return False


def _guard_timeout(deps: RoleDeps) -> int:
    try:
        return max(1, int(deps.env.get("BECKETT_GUARD_TIMEOUT") or deps.env.get("MASKS_GUARD_TIMEOUT") or 5))
    except (ValueError, TypeError):
        return 5


# ── Guard ─────────────────────────────────────────────────────────────────────


async def orient_synthesis_guard(deps: RoleDeps) -> GuardOutcome:
    """Trigger on SYNTHESIS_DAY (default 0=Sunday) when 7-day cooldown has elapsed."""
    syn_day = int(deps.env.get("SYNTHESIS_DAY", "0"))
    if int(datetime.now().strftime("%w")) != syn_day:
        return GuardOutcome(triggered=False, detail="wrong day")
    log = deps.personal_dir / ".synthesis.log"
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    if _recent_synthesis(log, cutoff):
        return GuardOutcome(triggered=False, detail="cooldown active")
    return GuardOutcome(triggered=True, detail="synthesis day")


# ── Agent ─────────────────────────────────────────────────────────────────────


async def orient_synthesis_agent(
    deps: RoleDeps, guard: GuardOutcome, context: dict | None = None
) -> dict:
    """Run the orient synthesis agent.

    The agent reads observations across roles and writes Synthesis/ entries.
    Post-run housekeeping (Rule 7): .synthesis.log update written by this function,
    not inside the LLM call.
    """
    if deps.role != "personal":
        return {
            "patterns_found": 0,
            "written": 0,
            "stale_updated": 0,
            "detail": "requires personal role",
        }

    phase_context = ""
    if context and context.get("_phase_triggers"):
        phase_context = f"\nPhase trigger context: {context['_phase_triggers']}"

    prompt = (
        f"Role: {deps.role}\n"
        f"Trigger: {guard.detail}{phase_context}\n\n"
        "Synthesize cross-role memory patterns and write Synthesis/ entries."
    )

    fallback: dict = {"patterns_found": 0, "written": 0, "stale_updated": 0}

    # Fallback: write a placeholder synthesis entry when no model is configured
    if not deps.env.get("BECKETT_MODEL", "").strip():
        llm_cmd = (
            deps.env.get("BECKETT_LLM_CMD", "").strip()
            or deps.env.get("MASKS_LLM_CMD", "").strip()
        )
        if llm_cmd:
            from beckett.loop.claude import invoke_claude

            invoke_claude(deps, prompt)

        now = datetime.now(timezone.utc)
        content = "\n".join([
            "# Cross-role synthesis",
            "",
            "**Status:** current",
            "",
            "## Pattern",
            "",
            "Automated synthesis placeholder entry.",
            "",
            "## Evidence",
            "",
            f"- ({deps.role}) {now.date()} — `Memory/` — loop-triggered synthesis",
        ])
        try:
            write_memory(
                deps,
                "Synthesis/loop-synthesis-placeholder",
                content,
                allow_personal_synthesis=True,
            )
            result = {"patterns_found": 1, "written": 1, "stale_updated": 0}
        except Exception:
            result = fallback
    else:
        result = await run_agent(_synthesis_agent, prompt, deps, fallback_result=fallback)

    # Rule 7: housekeeping — update .synthesis.log after agent run
    log = deps.personal_dir / ".synthesis.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = result.get("written", 0)
    stale = result.get("stale_updated", 0)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"SYNTHESIS {now_str} — {written} patterns found, {stale} updated\n")

    return result
