"""Resolve base directory and Beckett framework root."""

from __future__ import annotations

import os
from pathlib import Path


def load_base_env_mask(base: Path) -> str | None:
    """Read MASKS_BASE= from base/.env if present."""
    env_path = base / ".env"
    if not env_path.is_file():
        return None
    try:
        text = env_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("MASKS_BASE="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def resolve_base_path() -> Path:
    """Roles parent: MASKS_BASE env → Desktop/.env MASKS_BASE= → Desktop → home."""
    if os.environ.get("MASKS_BASE"):
        return Path(os.environ["MASKS_BASE"]).expanduser().resolve()
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        masked = load_base_env_mask(desktop)
        if masked:
            return Path(masked).expanduser().resolve()
        return desktop
    return Path.home()


def resolve_framework_root() -> Path:
    """Bundled ``_data/`` (guards, templates). Set ``BECKETT_ROOT`` to override for dev."""
    if os.environ.get("BECKETT_ROOT"):
        return Path(os.environ["BECKETT_ROOT"]).expanduser().resolve()
    return Path(__file__).resolve().parent / "_data"
