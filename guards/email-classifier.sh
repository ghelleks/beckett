#!/usr/bin/env bash
set -euo pipefail

command -v gws >/dev/null 2>&1 || exit 1

GWS_ACC="${GWS_PROFILE:-${MASKS_ROLE:-work}}"

if gws gmail triage --account "$GWS_ACC" 2>/dev/null | grep -q .; then
  exit 0
fi

exit 1
