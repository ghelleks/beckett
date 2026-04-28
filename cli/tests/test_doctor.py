from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import click
import pytest

from beckett.doctor_cmd import doctor_cmd


def _seed_role(base, name: str, spec: str | None = None, *, ooda_only: bool = False) -> None:
    role = base / name
    role.mkdir(parents=True, exist_ok=True)
    (role / "ROLE.md").write_text("# role\n", encoding="utf-8")
    if spec is not None:
        (role / "loop.yaml").write_text(spec, encoding="utf-8")
    if ooda_only:
        (role / "OODA.md").write_text("# OODA\n", encoding="utf-8")


def test_doctor_json_includes_loop_checks(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    _seed_role(
        tmp_path,
        "work",
        "observe: {entries: [{id: ooda-observe, agent: ooda-observe}]}\norient: {entries: []}\nact: {entries: []}\n",
    )
    buf = StringIO()
    with patch("sys.stdout", buf):
        doctor_cmd(json_out=True)
    data = json.loads(buf.getvalue())
    ids = {c["id"] for c in data["checks"]}
    assert "loop_spec" in ids
    assert "registry" in ids
    assert "model_env" in ids
    assert "prefect_cli" not in ids


def test_doctor_fails_ooda_only_role(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("MASKS_BASE", str(tmp_path))
    _seed_role(tmp_path, "work", ooda_only=True)
    with pytest.raises(click.exceptions.Exit):
        doctor_cmd(json_out=False)
