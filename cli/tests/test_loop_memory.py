from __future__ import annotations

from beckett.loop.deps import RoleDeps
from beckett.loop.memory_tools import read_memory_file, write_memory
from beckett.loop.spec import LoopSpec


def _deps(tmp_path) -> RoleDeps:
    base = tmp_path / "base"
    role = base / "work"
    personal = base / "personal"
    (role / "Memory").mkdir(parents=True, exist_ok=True)
    (personal / "Memory").mkdir(parents=True, exist_ok=True)
    return RoleDeps(
        role="work",
        role_dir=role,
        masks_base=base,
        personal_dir=personal,
        db_path=None,
        env={},
        loop_spec=LoopSpec(),
    )


def test_write_memory_creates_file(tmp_path) -> None:
    deps = _deps(tmp_path)
    out = write_memory(deps, "people/alice", "# Alice")
    assert out.is_file()
    assert "Alice" in out.read_text(encoding="utf-8")


def test_read_memory_missing_returns_none(tmp_path) -> None:
    deps = _deps(tmp_path)
    assert read_memory_file(deps, "does/not/exist") is None
