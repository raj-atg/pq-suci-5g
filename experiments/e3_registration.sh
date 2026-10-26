#!/usr/bin/env bash
# E3/E6: single-UE registration latency, RUNS runs per scheme, on the running core.
# Usage: CORE=stock|pq experiments/e3_registration.sh RUNS SCHEME...   (SCHEME: null profileA profileB pq)
# Raw: results/raw/e3/<core>/<scheme>/run_NN.*  CSV: results/processed/e3_registration.csv (appended)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/env.sh
source "$HERE/../scripts/env.sh"
RUNS="$1"; shift
OUT_CSV="$ROOT/results/processed/e3_registration.csv"

for scheme in "$@"; do
  dir="$ROOT/results/raw/e3/$CORE/$scheme"
  mkdir -p "$dir"
  for i in $(seq -w 1 "$RUNS"); do
    [[ -f "$dir/run_$i.status" ]] && grep -q "success=1" "$dir/run_$i.status" && continue
    "$HERE/run_registration.sh" -c "$ROOT/config/ueransim/ue-$scheme.yaml" -o "$dir/run_$i" -t 30 || true
  done
  "$ROOT/.venv/bin/python" "$HERE/parse_ngap.py" --scheme "$scheme" --core "$CORE" \
    --out "$OUT_CSV" --append "$dir"/run_*.pcap
done
