#!/usr/bin/env bash
# Copy the repository's files (tracked and untracked-but-not-ignored, so no builds or venv)
# to a Windows folder, so they can be browsed in File Explorer. WSL only; on plain Linux,
# or without config/export.env, it does nothing. Never deletes files in the target.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/config/export.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "sync_to_windows: no config/export.env, skipping (see config/export.env.example)"
  exit 0
fi
# shellcheck source=/dev/null
source "$ENV_FILE"
if [[ -z "${WINDOWS_MIRROR_DIR:-}" || ! -d /mnt/c ]]; then
  echo "sync_to_windows: not on WSL or WINDOWS_MIRROR_DIR unset, skipping"
  exit 0
fi

mkdir -p "$WINDOWS_MIRROR_DIR"
cd "$ROOT"
git ls-files --cached --others --exclude-standard -z \
  | rsync -rt --from0 --files-from=- --no-perms --no-owner --no-group ./ "$WINDOWS_MIRROR_DIR/"
echo "synced to $WINDOWS_MIRROR_DIR ($(wslpath -w "$WINDOWS_MIRROR_DIR" 2>/dev/null || true))"
