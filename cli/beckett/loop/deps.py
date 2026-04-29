"""Role dependency loading for loop runtime."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from beckett.env_util import merge_env_for_role
from beckett.loop.spec import LoopSpec, load_loop_spec
from beckett.paths import resolve_base_path
from beckett.role_path import resolve_role_dir


class RoleDeps(BaseModel):
    role: str
    role_dir: Path
    masks_base: Path
    personal_dir: Path
    db_path: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    loop_spec: LoopSpec


def build_role_deps(role_target: str, explicit_spec: str | None = None) -> RoleDeps:
    role_dir = resolve_role_dir(role_target).resolve()
    masks_base = role_dir.parent
    env = merge_env_for_role(masks_base, role_dir)
    spec = load_loop_spec(role_dir, explicit_spec=explicit_spec)
    db_raw = env.get("MCP_MEMORY_DB_PATH", "").strip()
    db_path = Path(db_raw).expanduser().resolve() if db_raw else None
    return RoleDeps(
        role=role_dir.name,
        role_dir=role_dir,
        masks_base=masks_base,
        personal_dir=masks_base / "personal",
        db_path=db_path,
        env=env,
        loop_spec=spec,
    )


def build_all_role_deps(explicit_spec: str | None = None) -> list[RoleDeps]:
    """Build deps for all roles under MASKS_BASE."""
    from beckett.roles import iter_role_dirs

    out: list[RoleDeps] = []
    for role_dir in iter_role_dirs(resolve_base_path()):
        out.append(build_role_deps(str(role_dir), explicit_spec=explicit_spec))
    return out
