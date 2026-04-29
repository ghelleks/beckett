"""Shared helpers for invoking the gws CLI from guard and agent tool functions."""

from __future__ import annotations

from pathlib import Path

from beckett.loop.deps import RoleDeps


def gws_env(deps: RoleDeps) -> dict[str, str]:
    """Return a subprocess env with GOOGLE_WORKSPACE_CLI_CONFIG_DIR set.

    Maps GWS_PROFILE (e.g. 'personal', 'work') to ~/.config/gws-<profile>.
    Falls back to role name when GWS_PROFILE is not set.
    """
    profile = deps.env.get("GWS_PROFILE", deps.role)
    config_dir = str(Path(f"~/.config/gws-{profile}").expanduser())
    env = dict(deps.env)
    env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = config_dir
    return env


def guard_timeout(deps: RoleDeps) -> int:
    """Return guard subprocess timeout from env (BECKETT_GUARD_TIMEOUT, default 5s)."""
    for key in ("BECKETT_GUARD_TIMEOUT", "MASKS_GUARD_TIMEOUT"):
        raw = deps.env.get(key, "").strip()
        if raw:
            try:
                return max(1, int(raw))
            except ValueError:
                pass
    return 5
