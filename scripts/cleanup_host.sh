#!/usr/bin/env bash
# Undo the host changes left by a test session (needs sudo). Idempotent.
#   - ip rules UERANSIM adds per UE tunnel ("from 10.45.x.x lookup rt_uesimtunN"); it does not
#     remove them when nr-ue is stopped
#   - the UPF tunnel interface ogstun
#   - /etc/iproute2/ (created for UERANSIM on Ubuntu 26.04, see docs/decisions.md D8), only if
#     it holds nothing beyond the distro default rt_tables and UERANSIM's rt_uesimtun entries
# Run it after scripts/stop_core.sh.
set -euo pipefail

mapfile -t prios < <(ip -o rule show | awk -F: '/from 10\.45\./ {print $1}')
for p in "${prios[@]}"; do
  sudo ip rule del priority "$p"
done
echo "removed ${#prios[@]} UE ip rules"

if ip link show ogstun >/dev/null 2>&1; then
  sudo ip link delete ogstun
  echo "removed ogstun"
fi

RT=/etc/iproute2/rt_tables
DEFAULT=/usr/share/iproute2/rt_tables
if [[ -d /etc/iproute2 ]]; then
  extra_files="$(find /etc/iproute2 -mindepth 1 ! -path "$RT" | wc -l)"
  if [[ "$extra_files" -eq 0 && -f "$DEFAULT" ]] \
     && diff -q <(grep -v 'rt_uesimtun' "$RT" | grep -v '^$') <(grep -v '^$' "$DEFAULT") >/dev/null; then
    sudo rm -r /etc/iproute2
    echo "removed /etc/iproute2"
  else
    echo "kept /etc/iproute2: it contains more than the default rt_tables and UERANSIM entries" >&2
  fi
fi
