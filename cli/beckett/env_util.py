"""Minimal .env parsing (no python-dotenv hard dependency for core paths)."""

from __future__ import annotations

import os
from pathlib import Path


def apply_env_file(path: Path, target: dict[str, str] | None = None) -> dict[str, str]:
    """Parse KEY=VALUE lines into target dict (default: new dict)."""
    if target is None:
        target = {}
    if not path.is_file():
        return target
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return target
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("export "):
            raw = raw[7:].strip()
        if "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            target[k] = v
    return target


def merge_env_for_role(base: Path, role_dir: Path) -> dict[str, str]:
    """Base .env then role .env (role wins). Includes os.environ as lowest layer."""
    out = dict(os.environ)
    apply_env_file(base / ".env", out)
    apply_env_file(role_dir / ".env", out)
    return out
