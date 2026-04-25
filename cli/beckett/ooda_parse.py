"""Parse OODA.md agenda sections for skill slugs (shared by doctor, beckett run)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

_PHASE = re.compile(r"^###\s+(Observe|Orient|Act)\s*$")
_ANY_H3 = re.compile(r"^###\s+")
_NUMBERED = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _strip_item(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] == "`" and s[-1] == "`":
        s = s[1:-1].strip()
    for sep in (" — ", " -- ", " # "):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
    return s


def extract_agenda_skills(
    ooda_path: Path,
    warn: Callable[[str, int, str], None] | None = None,
) -> list[str]:
    """
    Forward-scan OODA.md for numbered skills under Observe/Orient/Act.
    Returns slugs in document order, first occurrence only per slug.
    """
    if not ooda_path.is_file():
        return []
    text = ooda_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    phase: str | None = None
    seen: set[str] = set()
    out: list[str] = []
    for i, line in enumerate(lines, start=1):
        ph = _PHASE.match(line)
        if ph:
            phase = ph.group(1).lower()
            continue
        if _ANY_H3.match(line) and not _PHASE.match(line):
            phase = None
            continue
        if phase is None:
            continue
        nm = _NUMBERED.match(line)
        if nm:
            raw_item = nm.group(2)
            item = _strip_item(raw_item)
            if _SLUG.match(item):
                if item not in seen:
                    seen.add(item)
                    out.append(item)
            elif warn:
                warn("WARN_SKIP_AGENDA_LINE", i, line)
            continue
        stripped = line.strip()
        if stripped.startswith("-") or (stripped and not stripped[0].isdigit()):
            if stripped.startswith("-") and warn:
                warn("WARN_MALFORMED_AGENDA_LINE", i, line)
    return out
