#!/usr/bin/env bash
# Stop the processes started by start_core.sh (by pid file only) and MongoDB. Idempotent.
set -euo pipefail
# shellcheck source=scripts/env.sh
source "$(dirname "$0")/env.sh"

stop_pid() {
  local pidf="$1" use_sudo="${2:-}"
  [[ -f "$pidf" ]] || return 0
  local pid
  pid="$(cat "$pidf")"
  if kill -0 "$pid" 2>/dev/null || { [[ -n "$use_sudo" ]] && sudo kill -0 "$pid" 2>/dev/null; }; then
    ${use_sudo:+sudo} kill "$pid" 2>/dev/null || true
    for _ in $(seq 50); do
      ${use_sudo:+sudo} kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
  fi
  rm -f "$pidf"
}

for ((i = ${#NFS[@]} - 1; i >= 0; i--)); do
  nf="${NFS[$i]}"
  if [[ "$nf" == upf ]]; then stop_pid "$RUNTIME/pid/$nf.pid" sudo; else stop_pid "$RUNTIME/pid/$nf.pid"; fi
done
stop_pid "$RUNTIME/pid/mongod.pid"
echo "core stopped"
