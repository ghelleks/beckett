from __future__ import annotations

import pytest

from beckett.loop.spec import LoopConfigError, detect_spec_source, load_loop_spec


def _mk_role(base, name: str):
    role = base / name
    role.mkdir(parents=True, exist_ok=True)
    (role / "ROLE.md").write_text("# role\n", encoding="utf-8")
    return role


def test_load_yaml_spec(tmp_path) -> None:
    role = _mk_role(tmp_path, "work")
    (role / "loop.yaml").write_text(
        "observe: {entries: [{id: ooda-observe, agent: ooda-observe}]}\norient: {entries: []}\nact: {entries: []}\n",
        encoding="utf-8",
    )
    spec = load_loop_spec(role)
    assert len(spec.observe.entries) == 1


def test_ooda_not_supported(tmp_path) -> None:
    role = _mk_role(tmp_path, "work")
    (role / "OODA.md").write_text("# OODA\n", encoding="utf-8")
    with pytest.raises(LoopConfigError):
        load_loop_spec(role)


def test_detect_spec_source(tmp_path) -> None:
    role = _mk_role(tmp_path, "work")
    (role / "loop.json").write_text('{"observe":{"entries":[]},"orient":{"entries":[]},"act":{"entries":[]}}', encoding="utf-8")
    src, _ = detect_spec_source(role)
    assert src == "loop.json"
