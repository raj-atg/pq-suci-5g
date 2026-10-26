#!/usr/bin/env bash
# E1 native: run liboqs speed_kem for ML-KEM and parse into results/processed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/third_party/liboqs/build/tests/speed_kem"
RAW="$ROOT/results/raw/e1/speed_kem.txt"
mkdir -p "$ROOT/results/raw/e1" "$ROOT/results/processed"

echo "# command (per algorithm): ${BIN#"$ROOT"/} --duration 3 <alg>" >"$RAW"
for alg in ML-KEM-512 ML-KEM-768 ML-KEM-1024; do
  "$BIN" --duration 3 "$alg" | tee -a "$RAW"
done
"$ROOT/.venv/bin/python" "$ROOT/bench/parse_speed_kem.py" "$RAW" \
  "$ROOT/results/processed/e1_native_liboqs.csv"
