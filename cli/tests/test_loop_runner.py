from __future__ import annotations

import json

from beckett.loop.deps import build_role_deps
from beckett.loop.runner import run_loop_cycle


def _init_repo(path):
    import subprocess

    subprocess.run(["git", "init", str(path)], check=False, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=False)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=False)


def test_run_loop_cycle_writes_last_run(tmp_path, monkeypatch) -> None:
    base = tmp_path / "base"
    role = base / "work"
    role.mkdir(parents=True, exist_ok=True)
    (role / "ROLE.md").write_text("# role\n", encoding="utf-8")
    (role / "Memory").mkdir(parents=True, exist_ok=True)
    (role / "loop.yaml").write_text(
        "observe: {entries: [{id: ooda-observe, agent: ooda-observe}]}\norient: {entries: []}\nact: {entries: []}\n",
        encoding="utf-8",
    )
    _init_repo(role)
    monkeypatch.setenv("MASKS_BASE", str(base))

    deps = build_role_deps("work")
    out = run_loop_cycle(deps, once=True)
    assert out.role == "work"
    state = role / ".ooda-state" / "last-run.json"
    assert state.is_file()
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["role"] == "work"
