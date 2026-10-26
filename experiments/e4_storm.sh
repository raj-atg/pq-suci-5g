#!/usr/bin/env bash
# E4/E6: attach storm. N simultaneous UEs (nr-ue -n N) per scheme, REPS repetitions.
# Records per-UE latency (from NGAP) and UDM CPU: a pidstat time series and the exact CPU time
# the UDM process used during the run (utime+stime delta from /proc/<pid>/stat).
# Usage: CORE=stock|pq experiments/e4_storm.sh REPS "1 10 50 100" SCHEME...
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/env.sh
source "$HERE/../scripts/env.sh"
REPS="$1"; NS="$2"; shift 2
CPU_CSV="$ROOT/results/processed/e4_udm_cpu.csv"
LAT_CSV="$ROOT/results/processed/e4_storm.csv"
CLK_TCK="$(getconf CLK_TCK)"
[[ -f "$CPU_CSV" ]] || echo "scheme,core,n_ues,rep,udm_cpu_s,wall_s,udm_cpu_pct_avg,sessions_ok" > "$CPU_CSV"

udm_ticks() { awk '{print $14 + $15}' "/proc/$UDM_PID/stat"; }

for scheme in "$@"; do
  # Fresh core per scheme: the Open5GS AUSF keeps one context per SUCI string and our UEs are
  # stopped without deregistering, so a long series of protected registrations would exhaust
  # its context pool (global max.ue). One scheme's storms stay well below that limit.
  "$ROOT/scripts/stop_core.sh" >/dev/null
  "$ROOT/scripts/start_core.sh" >/dev/null
  UDM_PID="$(cat "$RUNTIME/pid/udm.pid")"
  for n in $NS; do
    for rep in $(seq 1 "$REPS"); do
      dir="$ROOT/results/raw/e4/$CORE/$scheme/n$n"
      mkdir -p "$dir"
      out="$dir/rep_$rep"
      [[ -f "$out.status" ]] && grep -q "success=1" "$out.status" && continue
      pidstat -h -u -p "$UDM_PID" 1 >"$out.pidstat" &
      pid_stat=$!
      t0="$(date +%s.%N)"; c0="$(udm_ticks)"
      "$HERE/run_registration.sh" -c "$ROOT/config/ueransim/ue-$scheme.yaml" -o "$out" -n "$n" -t 120 || true
      t1="$(date +%s.%N)"; c1="$(udm_ticks)"
      kill "$pid_stat" 2>/dev/null || true
      wait "$pid_stat" 2>/dev/null || true
      sed -i "s/($(hostname))/(host)/" "$out.pidstat"  # keep the machine name out of the results
      ok="$(sed -n 's/.*sessions_ok=\([0-9]*\/[0-9]*\).*/\1/p' "$out.status")"
      awk -v s="$scheme" -v c="$CORE" -v n="$n" -v r="$rep" -v c0="$c0" -v c1="$c1" \
          -v t0="$t0" -v t1="$t1" -v hz="$CLK_TCK" -v ok="$ok" 'BEGIN {
        cpu = (c1 - c0) / hz; wall = t1 - t0
        printf "%s,%s,%d,%d,%.3f,%.3f,%.2f,%s\n", s, c, n, r, cpu, wall, 100 * cpu / wall, ok }' >> "$CPU_CSV"
      "$ROOT/.venv/bin/python" "$HERE/parse_ngap.py" --scheme "$scheme" --core "$CORE" \
        --n-ues "$n" --out "$LAT_CSV" --append "$out.pcap"
    done
  done
done
