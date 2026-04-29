"""Prompt-stack builder and subprocess helper for LLM invocations."""

from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path

from beckett.loop.deps import RoleDeps

log = logging.getLogger(__name__)

# Matches Pirandello hooks/start.sh section order exactly.
_STACK_SECTIONS: list[tuple[str, str, str]] = [
    ("=== GLOBAL AGENTS ===", "masks_base", "AGENTS.md"),
    ("=== SELF ===", "personal_dir", "SELF.md"),
    ("=== ROLE ===", "role_dir", "ROLE.md"),
    ("=== ROLE AGENTS ===", "role_dir", "AGENTS.md"),
    ("=== CONTEXT ===", "role_dir", "CONTEXT.md"),
    ("=== ARCHIVE INDEX ===", "role_dir", "Archive/INDEX.md"),
    ("=== MEMORY INDEX ===", "role_dir", "Memory/INDEX.md"),
    ("=== REFERENCE INDEX ===", "role_dir", "Reference/INDEX.md"),
]


def build_prompt_stack(deps: RoleDeps) -> str:
    """Assemble the Pirandello prompt stack for a role.

    Reads optional files in the same order as hooks/start.sh. Missing files are
    silently skipped so partial role configurations still work.
    """
    parts: list[str] = []
    for header, base_attr, rel in _STACK_SECTIONS:
        root: Path = getattr(deps, base_attr)
        p = root / rel
        if p.is_file():
            parts.append(header)
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
            parts.append("")
    return "\n".join(parts)


def _llm_argv(deps: RoleDeps) -> list[str]:
    """Return the LLM subprocess argv, respecting env overrides (GAP 4)."""
    for key in ("BECKETT_LLM_CMD", "MASKS_LLM_CMD"):
        cmd = deps.env.get(key, "").strip()
        if cmd:
            return shlex.split(cmd)
    return ["claude", "--print", "--output-format", "text"]


def _llm_timeout(deps: RoleDeps) -> int | None:
    """Parse BECKETT_LLM_TIMEOUT; 0 = unlimited. Default 1800s."""
    raw = deps.env.get("BECKETT_LLM_TIMEOUT", "1800").strip()
    try:
        v = int(raw)
        return None if v <= 0 else v
    except ValueError:
        return 1800


def invoke_claude(deps: RoleDeps, skill_prompt: str, *, timeout: int | None = None) -> str:
    """Invoke the LLM subprocess with the Pirandello prompt stack prepended.

    Closes GAPs 2, 4, 5, 9:
    - Builds prompt stack from role filesystem (GAP 2)
    - Respects BECKETT_LLM_CMD / MASKS_LLM_CMD (GAP 4)
    - Logs stderr when BECKETT_LLM_DEBUG=1 (GAP 5)
    - Injects MASKS_ROLE, MASKS_BASE, BECKETT_ROLE_DIR env vars (GAP 9)
    - Wraps in OpenShell sandbox when BECKETT_OPENSHELL_POLICY is set (Task 1c)

    Non-zero exit is logged but not raised (matches run_cmd.py behavior).
    """
    stack = build_prompt_stack(deps)
    stdin_text = f"{stack}\n---\n{skill_prompt}"

    env = dict(deps.env)
    env["MASKS_BASE"] = str(deps.masks_base)
    env["MASKS_ROLE"] = deps.role
    env["MASKS_ROLE_DIR"] = str(deps.role_dir)
    env["BECKETT_ROLE"] = deps.role
    env["BECKETT_ROLE_DIR"] = str(deps.role_dir)

    policy = env.get("BECKETT_OPENSHELL_POLICY", "").strip()
    base_argv = _llm_argv(deps)
    if policy:
        argv = ["openshell", "run", "--policy", policy, "--"] + base_argv
    else:
        argv = base_argv

    debug = env.get("BECKETT_LLM_DEBUG", "").strip() == "1"
    tmo = timeout if timeout is not None else _llm_timeout(deps)

    try:
        proc = subprocess.run(
            argv,
            input=stdin_text,
            cwd=str(deps.role_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=tmo,
        )
        if debug and proc.stderr.strip():
            log.debug("LLM stderr role=%s: %s", deps.role, proc.stderr[:8192])
        if proc.returncode != 0:
            log.warning(
                "LLM subprocess exited %d for role=%s argv=%s",
                proc.returncode,
                deps.role,
                argv[:2],
            )
        return proc.stdout
    except subprocess.TimeoutExpired:
        log.error("LLM subprocess timed out (%ss) for role=%s", tmo, deps.role)
        raise
