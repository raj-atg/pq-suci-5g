#!/usr/bin/env bash
# Fail if any given file (default: all git-tracked and untracked non-ignored files) contains U+2014.
# The character is built from bytes so this script never contains it.
set -euo pipefail

EMDASH="$(printf '\xe2\x80\x94')"
cd "$(dirname "$(readlink -f "$0")")/.."

if [[ $# -gt 0 ]]; then
  files=("$@")
else
  mapfile -t files < <(git ls-files --cached --others --exclude-standard)
fi

status=0
for f in "${files[@]}"; do
  [[ -f "$f" ]] || continue
  if grep -nF -- "$EMDASH" "$f" >/dev/null 2>&1; then
    grep -nF -- "$EMDASH" "$f" | sed "s|^|$f:|" >&2
    status=1
  fi
  # File names too
  if [[ "$f" == *"$EMDASH"* ]]; then
    echo "em dash in file name: $f" >&2
    status=1
  fi
done
if [[ $status -ne 0 ]]; then
  echo "ERROR: em dash (U+2014) found. Use a comma, colon, parentheses or a hyphen." >&2
fi
exit $status
