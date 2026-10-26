#!/usr/bin/env bash
# One registration run: capture NGAP + SBI on lo, start a gNB and N UEs, wait until every UE
# has a PDU session (or timeout), optionally ping through uesimtun0, then stop everything we
# started. The core must already be running (scripts/start_core.sh).
#
# Usage: run_registration.sh -c UE_CONFIG -o OUT_PREFIX [-n N] [-u UERANSIM_BUILD] [-t TIMEOUT] [-p]
#   writes OUT_PREFIX.pcap, OUT_PREFIX.ue.log, OUT_PREFIX.gnb.log, OUT_PREFIX.status
set -euo pipefail
# shellcheck source=scripts/env.sh
source "$(dirname "$0")/../scripts/env.sh"

N=1 TIMEOUT=60 PING=0 CFG="" OUT=""
while getopts "c:o:n:u:t:p" opt; do
  case "$opt" in
    c) CFG="$OPTARG" ;; o) OUT="$OPTARG" ;; n) N="$OPTARG" ;; u) UERANSIM="$OPTARG" ;;
    t) TIMEOUT="$OPTARG" ;; p) PING=1 ;; *) exit 2 ;;
  esac
done
[[ -n "$CFG" && -n "$OUT" ]] || { echo "usage: $0 -c UE_CONFIG -o OUT_PREFIX [-n N]" >&2; exit 2; }
mkdir -p "$(dirname "$OUT")"

# For the ping check the UE tunnel goes into its own network namespace: on a single host the
# UPF tun address (10.45.0.1) is local, so a ping from the root namespace never enters GTP-U.
if [[ "$PING" -eq 1 ]]; then
  sed 's/^useNamespace: false/useNamespace: true/' "$CFG" >"$OUT.ue-config.yaml"
  CFG="$OUT.ue-config.yaml"
fi

TSHARK_PID="" GNB_PID="" UE_PID=""
cleanup() {
  [[ -n "$UE_PID" ]] && sudo kill "$UE_PID" 2>/dev/null || true
  sleep 0.5
  [[ -n "$GNB_PID" ]] && kill "$GNB_PID" 2>/dev/null || true
  sleep 0.5
  [[ -n "$TSHARK_PID" ]] && sudo kill -INT "$TSHARK_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT

# dumpcap running as root cannot open files in the home directory, so it writes to stdout.
# shellcheck disable=SC2024  # intended: the redirect runs as our user
sudo tshark -q -i lo -f "sctp port 38412 or tcp port 7777" -w - >"$OUT.pcap" 2>/dev/null &
TSHARK_PID=$!
sleep 1.5

"$UERANSIM/nr-gnb" -c "$ROOT/config/ueransim/gnb.yaml" >"$OUT.gnb.log" 2>&1 &
GNB_PID=$!
sleep 1

# shellcheck disable=SC2024  # the log file is ours; nr-ue needs root for its TUN device
sudo "$UERANSIM/nr-ue" -c "$CFG" -n "$N" >"$OUT.ue.log" 2>&1 &
UE_PID=$!

ok=0
for _ in $(seq $((TIMEOUT * 10))); do
  done_count="$(grep -c "PDU Session establishment is successful" "$OUT.ue.log" || true)"
  if [[ "$done_count" -ge "$N" ]]; then ok=1; break; fi
  sleep 0.1
done

ping_result="skipped"
if [[ "$ok" -eq 1 && "$PING" -eq 1 ]]; then
  sleep 1
  ns="$(ip netns list | awk '/ueransim/ {print $1; exit}')"
  # shellcheck disable=SC2024  # the log file is ours
  if [[ -n "$ns" ]] && sudo ip netns exec "$ns" ping -I uesimtun0 -c 3 -W 2 10.45.0.1 >"$OUT.ping.log" 2>&1; then
    ping_result="ok"
  else
    ping_result="failed"
  fi
fi
sleep 1  # let the last SBI/NGAP messages reach the capture
echo "ue_config=$CFG n=$N sessions_ok=$done_count/$N success=$ok ping=$ping_result" | tee "$OUT.status"
