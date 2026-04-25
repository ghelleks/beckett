#!/usr/bin/env bash
set -euo pipefail

command -v td >/dev/null 2>&1 || exit 1

if td find-tasks --filter '(today | overdue) & (@agent | @decision)' 2>/dev/null | grep -q .; then
  exit 0
fi

exit 1
