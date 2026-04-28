from __future__ import annotations

from beckett.loop.deps import RoleDeps
from beckett.loop.skills.daily_briefer import daily_briefer_guard
from beckett.loop.spec import LoopSpec


def _deps(tmp_path) -> RoleDeps:
    base = tmp_path / "base"
    role = base / "work"
    personal = base / "personal"
    role.mkdir(parents=True, exist_ok=True)
    personal.mkdir(parents=True, exist_ok=True)
    return RoleDeps(
        role="work",
        role_dir=role,
        masks_base=base,
        personal_dir=personal,
        db_path=None,
        env={"DAILY_BRIEFER_TARGET": "00:00"},
        loop_spec=LoopSpec(),
    )


def test_daily_briefer_guard_returns_outcome(tmp_path) -> None:
    deps = _deps(tmp_path)
    out = __import__("asyncio").run(daily_briefer_guard(deps))
    assert out.triggered in {True, False}
