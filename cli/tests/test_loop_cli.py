from __future__ import annotations

from typer.testing import CliRunner

from beckett.cli import app


def test_once_routes_to_runner(monkeypatch) -> None:
    called = {"once": False}

    def _fake_once(role_target=None, spec_path=None):
        called["once"] = True

    monkeypatch.setattr("beckett.cli.run_loop_once", _fake_once)
    runner = CliRunner()
    res = runner.invoke(app, ["loop", "--once", "--role-target", "work"])
    assert res.exit_code == 0
    assert called["once"] is True


def test_daemon_routes_to_runner(monkeypatch) -> None:
    called = {"daemon": False}

    def _fake_daemon(role_target=None, interval="15m", spec_path=None):
        called["daemon"] = True

    monkeypatch.setattr("beckett.cli.run_loop_daemon", _fake_daemon)
    runner = CliRunner()
    res = runner.invoke(app, ["loop", "--role-target", "work", "--interval", "5m"])
    assert res.exit_code == 0
    assert called["daemon"] is True
