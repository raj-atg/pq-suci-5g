#!/usr/bin/env bash
# Run every experiment in order. Needs the builds (make build), keys (make keys) and sudo.
#   E1, E2, E5: microbenchmarks and models (core stopped, idle machine)
#   E3 check:   stock core, null and Profile A (shows the patches do not slow these down)
#   E3/E6:      patched core, single-UE latency for null, Profile A, Profile B, scheme 12
#   E4/E6:      patched core, attach storms of 1/10/50/100 UEs, UDM CPU
# Environment: E3_RUNS (default 30), E3_CHECK_RUNS (10), E4_REPS (3), E4_NS ("1 10 50 100")
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export OQS_INSTALL_PATH="$ROOT/third_party/install/liboqs"
PY="$ROOT/.venv/bin/python"
E3_RUNS="${E3_RUNS:-30}" E3_CHECK_RUNS="${E3_CHECK_RUNS:-10}" E4_REPS="${E4_REPS:-3}"
E4_NS="${E4_NS:-1 10 50 100}"

echo "== E1/E2/E5 (core stopped)"
scripts/stop_core.sh >/dev/null
bench/e1_repeat.sh 3
bash bench/e1_native.sh
"$PY" experiments/e2_sizes.py
"$PY" experiments/e5_models.py

echo "== E3 check on the stock core"
CORE=stock scripts/start_core.sh
scripts/add_subscribers.sh 120
CORE=stock experiments/e3_registration.sh "$E3_CHECK_RUNS" null profileA
scripts/stop_core.sh >/dev/null

echo "== E3/E4/E6 on the patched core"
CORE=pq scripts/start_core.sh
CORE=pq experiments/e3_registration.sh "$E3_RUNS" null profileA profileB pq
cp runtime/log/udm.log results/raw/e3/pq/udm.log
CORE=pq experiments/e4_storm.sh "$E4_REPS" "$E4_NS" null profileA profileB pq
scripts/stop_core.sh >/dev/null

"$PY" experiments/parse_native_logs.py --ue-logs 'results/raw/e3/pq/*/*.ue.log' \
  --udm-log results/raw/e3/pq/udm.log
echo "== all experiments done"
