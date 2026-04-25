#!/usr/bin/env bash
# Exit 0 only on synthesis day (default Sunday) and outside 7-day cooldown.
set -euo pipefail

BASE="${BASE:-${MASKS_BASE:-}}"
if [[ -z "$BASE" ]]; then
  exit 1
fi

dow=$(date +%w)
syn_day="${SYNTHESIS_DAY:-0}"
if [[ "$dow" != "$syn_day" ]]; then
  exit 1
fi

LOG="$BASE/personal/.synthesis.log"
if [[ ! -f "$LOG" ]]; then
  exit 0
fi

export LOG_PATH="$LOG"
python3 <<'PY'
from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path

log = Path(os.environ["LOG_PATH"])
if not log.is_file():
    raise SystemExit(0)
now = dt.datetime.now(dt.timezone.utc)
cutoff = now - dt.timedelta(days=7)
pat = re.compile(r"^SYNTHESIS\s+(\S+)")
for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
    m = pat.match(line.strip())
    if not m:
        continue
    raw = m.group(1).replace("Z", "+00:00")
    ts = dt.datetime.fromisoformat(raw)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    if ts > cutoff:
        raise SystemExit(1)
raise SystemExit(0)
PY
