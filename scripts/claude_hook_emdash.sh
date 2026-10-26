#!/usr/bin/env bash
# Claude Code PostToolUse hook: check the file just written or edited for U+2014.
# Exit 2 sends the error back to Claude so it fixes the file.
set -euo pipefail
file="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')"
[[ -n "$file" && -f "$file" ]] || exit 0
if ! "$(dirname "$0")/check_no_emdash.sh" "$file"; then
  exit 2
fi
