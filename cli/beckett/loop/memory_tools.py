"""Filesystem memory write/read and semantic search helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from beckett.loop.deps import RoleDeps


class MemoryWriteError(RuntimeError):
    """Raised when a memory write violates policy."""


def _ensure_under(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise MemoryWriteError(f"path escapes root {root}: {path}") from exc


def _update_memory_index(memory_dir: Path) -> None:
    idx = memory_dir / "INDEX.md"
    if not idx.is_file():
        idx.write_text("| File | Summary | Tags |\n|------|---------|------|\n", encoding="utf-8")


def write_memory(
    deps: RoleDeps,
    subpath: str,
    content: str,
    *,
    allow_personal_synthesis: bool = False,
) -> Path:
    rel = Path(subpath)
    if rel.suffix != ".md":
        rel = rel.with_suffix(".md")

    target = (deps.role_dir / "Memory" / rel).resolve()
    role_memory_root = (deps.role_dir / "Memory").resolve()
    personal_synth_root = (deps.personal_dir / "Memory" / "Synthesis").resolve()

    if allow_personal_synthesis and str(rel).startswith("Synthesis/") and deps.role == "personal":
        target = (deps.personal_dir / "Memory" / rel).resolve()
        _ensure_under(target, personal_synth_root)
    else:
        _ensure_under(target, role_memory_root)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _update_memory_index(target.parent.parent if target.parent.name != "Memory" else target.parent)
    return target


def read_memory_file(deps: RoleDeps, subpath: str, *, role_scope: str = "current") -> str | None:
    rel = Path(subpath)
    if rel.suffix != ".md":
        rel = rel.with_suffix(".md")
    base = deps.role_dir if role_scope == "current" else deps.personal_dir
    target = (base / "Memory" / rel).resolve()
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8", errors="replace")


def search_memory(deps: RoleDeps, query: str, role_scope: str = "current") -> list[dict[str, Any]]:
    if deps.db_path is None:
        return []
    role_tag = deps.role if role_scope == "current" else "personal"
    try:
        from mcp_memory_service.storage.sqlite_vec import SqliteVecMemoryStorage
    except Exception:
        return []

    async def _run() -> list[dict[str, Any]]:
        storage = SqliteVecMemoryStorage(db_path=str(deps.db_path))
        await storage.initialize()
        try:
            rows = await storage.retrieve(query, tags=[f"role:{role_tag}"])
            return [r.model_dump(mode="json") if hasattr(r, "model_dump") else json.loads(json.dumps(r)) for r in rows]
        finally:
            await storage.close()

    import asyncio

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # already in event loop; in tests/runner this should not happen, return empty fallback
        return []


def commit_role_changes(role_dir: Path, message: str) -> bool:
    """Commit all repo changes for role; return True if commit created."""
    add = subprocess.run(["git", "-C", str(role_dir), "add", "-A"], capture_output=True, text=True)
    if add.returncode != 0:
        return False
    has_changes = subprocess.run(
        ["git", "-C", str(role_dir), "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
    )
    if has_changes.returncode == 0:
        return False
    commit = subprocess.run(["git", "-C", str(role_dir), "commit", "-m", message], capture_output=True, text=True)
    return commit.returncode == 0
