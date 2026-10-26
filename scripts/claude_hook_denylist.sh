#!/usr/bin/env bash
# Claude Code PreToolUse hook for Bash: block a short denylist of dangerous commands.
# Exit 2 blocks the tool call and shows the reason to Claude.
set -euo pipefail
cmd="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')"
# shellcheck disable=SC2016  # literal regexes, nothing should expand
patterns=(
  'rm[[:space:]]+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*[[:space:]]+(/|~|\$HOME|/mnt/c)/?([[:space:]]|$|\*)'
  'rm[[:space:]]+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*[[:space:]]+(/|~|\$HOME|/mnt/c)/?([[:space:]]|$|\*)'
  'git[[:space:]]+push.*[[:space:]](-f|--force[a-z-]*)([[:space:]]|$)'
  '(^|[[:space:];&|])mkfs'
  '(^|[[:space:];&|])dd[[:space:]]+if='
  'DENYLIST_SELFTEST'
)
for p in "${patterns[@]}"; do
  if [[ "$cmd" =~ $p ]]; then
    echo "BLOCKED by .claude denylist hook (pattern: $p). Ask the user first." >&2
    exit 2
  fi
done
exit 0
