#!/usr/bin/env bash
# Start MongoDB and the Open5GS 5G SA network functions with our configs. Idempotent:
# processes that are already running (per their pid file) are left alone.
set -euo pipefail
# shellcheck source=scripts/env.sh
source "$(dirname "$0")/env.sh"

mkdir -p "$RUNTIME"/{log,pid,db,open5gs}

is_running() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

# MongoDB with a local dbpath (no systemd).
if ! is_running "$RUNTIME/pid/mongod.pid"; then
  mongod --fork --dbpath "$RUNTIME/db" --bind_ip 127.0.0.1 --port 27017 \
    --logpath "$RUNTIME/log/mongod.log" --pidfilepath "$RUNTIME/pid/mongod.pid" >/dev/null
fi

# UPF tunnel device (only ogstun is touched).
if ! ip link show ogstun >/dev/null 2>&1; then
  sudo ip tuntap add name ogstun mode tun
fi
if ! ip -4 addr show ogstun | grep -q 10.45.0.1/16; then
  sudo ip addr add 10.45.0.1/16 dev ogstun
fi
sudo ip link set ogstun up

# Render configs.
for nf in "${NFS[@]}"; do
  sed -e "s|@RUNTIME@|$RUNTIME|g" -e "s|@KEYS@|$KEYS|g" \
    "$ROOT/config/open5gs/$nf.yaml" > "$RUNTIME/open5gs/$nf.yaml"
done

start_nf() {
  local nf="$1" pidf="$RUNTIME/pid/$1.pid"
  is_running "$pidf" && return 0
  local bin="$O5GS_PREFIX/bin/open5gs-${nf}d"
  if [[ "$nf" == upf ]]; then
    # shellcheck disable=SC2024  # the log file is ours; only the UPF needs root
    sudo -E env LD_LIBRARY_PATH="$LD_LIBRARY_PATH" "$bin" -c "$RUNTIME/open5gs/$nf.yaml" \
      >"$RUNTIME/log/$nf.stdout" 2>&1 &
  else
    "$bin" -c "$RUNTIME/open5gs/$nf.yaml" >"$RUNTIME/log/$nf.stdout" 2>&1 &
  fi
  echo $! > "$pidf"
}

for nf in "${NFS[@]}"; do
  start_nf "$nf"
  [[ "$nf" == nrf || "$nf" == scp ]] && sleep 1
done
sleep 3
for nf in "${NFS[@]}"; do
  is_running "$RUNTIME/pid/$nf.pid" || { echo "ERROR: $nf did not start, see $RUNTIME/log/$nf.stdout" >&2; exit 1; }
done
echo "core up: ${NFS[*]} (logs in $RUNTIME/log)"
