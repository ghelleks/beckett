from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from beckett.roles_cmd import roles_cmd


def _mk_role(base, name: str) -> None:
    role = base / name
    role.mkdir(parents=True, exist_ok=True)
    (role / "ROLE.md").write_text("# role\n", encoding="utf-8")


def test_roles_shows_loop_yaml(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    _mk_role(tmp_path, "work")
    (tmp_path / "work" / "loop.yaml").write_text(
        "observe: {entries: []}\norient: {entries: []}\nact: {entries: []}\n",
        encoding="utf-8",
    )
    buf = StringIO()
    with patch("sys.stdout", buf):
        roles_cmd(())
    out = buf.getvalue()
    assert "SPEC" in out
    assert "loop.yaml" in out


def test_roles_shows_unsupported_ooda(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    _mk_role(tmp_path, "work")
    (tmp_path / "work" / "OODA.md").write_text("# OODA\n", encoding="utf-8")
    buf = StringIO()
    with patch("sys.stdout", buf):
        roles_cmd(())
    assert "OODA.md (unsupported)" in buf.getvalue()
