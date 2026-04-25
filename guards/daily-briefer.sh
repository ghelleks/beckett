#!/usr/bin/env bash
set -euo pipefail

ROLE_DIR="${MASKS_ROLE_DIR:?MASKS_ROLE_DIR not set by beckett run}"

now_h=$(date +%H)
now_m=$(date +%M)
now_total=$((10#$now_h * 60 + 10#$now_m))
target=$((6 * 60 + 45))
delta=$((now_total - target))
if [[ $delta -lt 0 ]]; then delta=$(( -delta )); fi
[[ $delta -le 15 ]] || exit 1

mkdir -p "$ROLE_DIR/.ooda-state"
stamp="$ROLE_DIR/.ooda-state/daily-briefer-$(date +%Y-%m-%d)"
[[ ! -f "$stamp" ]] || exit 1

exit 0
