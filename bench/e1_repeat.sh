#!/usr/bin/env bash
# Repeat the Python microbenchmark (E1) R times on an idle machine and keep every run, so the
# run-to-run spread (CPU frequency scaling, WSL scheduling) is visible next to the values.
# Usage: bench/e1_repeat.sh [R]   (default 3)
# Output: results/raw/e1/repeat_<k>/, results/processed/e1_micro_python.csv (from the last run),
#         results/processed/e1_repeatability.csv (median per run and the spread across runs)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OQS_INSTALL_PATH="$ROOT/third_party/install/liboqs"
R="${1:-3}"
for k in $(seq 1 "$R"); do
  "$ROOT/.venv/bin/python" "$ROOT/bench/e1_micro.py"
  mkdir -p "$ROOT/results/raw/e1/repeat_$k"
  cp "$ROOT/results/processed/e1_micro_python.csv" "$ROOT/results/raw/e1/repeat_$k/"
  cp "$ROOT/results/raw/e1/env.txt" "$ROOT/results/raw/e1/repeat_$k/"
done
"$ROOT/.venv/bin/python" - "$ROOT" "$R" <<'PY'
"""Summarize per-run medians: one row per scheme and operation."""
import sys
from pathlib import Path

import pandas as pd

root, runs = Path(sys.argv[1]), int(sys.argv[2])
frames = []
for k in range(1, runs + 1):
    df = pd.read_csv(root / f"results/raw/e1/repeat_{k}/e1_micro_python.csv", keep_default_na=False)
    frames.append(df.assign(run=k))
d = pd.concat(frames)
g = d.groupby(["scheme", "operation"])["median_us"]
out = g.agg(runs="count", median_of_medians_us="median", min_median_us="min", max_median_us="max")
out.round(3).reset_index().to_csv(root / "results/processed/e1_repeatability.csv", index=False)
print(out.round(1).to_string())
PY
