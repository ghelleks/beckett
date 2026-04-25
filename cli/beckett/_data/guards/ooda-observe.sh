#!/usr/bin/env bash
set -euo pipefail

GWS_ACC="${GWS_PROFILE:-${MASKS_ROLE:-work}}"

if command -v gws >/dev/null 2>&1; then
  if gws gmail triage --account "$GWS_ACC" 2>/dev/null | grep -q .; then
    exit 0
  fi
fi

OBS_MARKER="${MASKS_ROLE_DIR:-.}/.ooda-pending/observer.txt"
if [[ -f "$OBS_MARKER" ]] && grep -q '[^[:space:]]' "$OBS_MARKER" 2>/dev/null; then
  exit 0
fi

exit 1
