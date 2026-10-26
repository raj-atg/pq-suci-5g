"""Native (C/C++) SUCI timings from the patched UERANSIM and Open5GS logs (E6).

The patches log one line per operation:
  UE  (UERANSIM): [SUCI] scheme=<id> output_bytes=<n> conceal_us=<t>
  UDM (Open5GS):  [SIDF] scheme=<id> suci_len=<n> supi=<supi> deconceal_us=<t>
The UE side covers ephemeral key / encapsulation + KDF + AES + HMAC; the SIDF side covers the
whole `ogs_supi_from_suci()` call (string parsing, hex decoding, decapsulation, KDF, MAC, AES).

Usage: python experiments/parse_native_logs.py --ue-logs 'results/raw/e3/pq/*/*.ue.log' \
           --udm-log results/raw/e3/pq/udm.log
Output: results/processed/e6_native_timings_raw.csv and e6_native_timings.csv (summary)
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UE_RE = re.compile(r"\[SUCI\] scheme=(\d+) output_bytes=(\d+) conceal_us=([\d.]+)")
SIDF_RE = re.compile(r"\[SIDF\] scheme=(\d+) suci_len=(\d+) supi=(\S+) deconceal_us=([\d.]+)")
SCHEME_NAMES = {"0": "null", "1": "profile-a", "2": "profile-b", "12": "mlkem768"}


def parse_ue(paths: list[str]) -> list[dict[str, str]]:
    """Collect UE-side conceal timings."""
    rows = []
    for path in paths:
        for match in UE_RE.finditer(Path(path).read_text(errors="replace")):
            rows.append(
                {
                    "side": "ue_conceal",
                    "scheme": SCHEME_NAMES.get(match[1], match[1]),
                    "size": match[2],
                    "us": match[3],
                    "source": Path(path).name,
                }
            )
    return rows


def parse_sidf(path: Path) -> list[dict[str, str]]:
    """Collect SIDF de-conceal timings (failed de-concealments are skipped)."""
    rows = []
    for match in SIDF_RE.finditer(path.read_text(errors="replace")):
        if match[3] == "FAILED":
            continue
        rows.append(
            {
                "side": "sidf_deconceal",
                "scheme": SCHEME_NAMES.get(match[1], match[1]),
                "size": match[2],
                "us": match[4],
                "source": path.name,
            }
        )
    return rows


def summarize(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Median, p95 and mean per (side, scheme)."""
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        groups[(r["side"], r["scheme"])].append(float(r["us"]))
    out = []
    for (side, scheme), values in sorted(groups.items()):
        values.sort()
        p95 = values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))]
        out.append(
            {
                "impl": "c-native",
                "side": side,
                "scheme": scheme,
                "n": len(values),
                "median_us": round(statistics.median(values), 1),
                "p95_us": round(p95, 1),
                "mean_us": round(statistics.fmean(values), 1),
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write rows with the keys of the first row as header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Entry point."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ue-logs", required=True, help="glob pattern for UE logs")
    p.add_argument("--udm-log", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, default=ROOT / "results/processed")
    args = p.parse_args()
    raw = parse_ue(sorted(glob.glob(args.ue_logs))) + parse_sidf(args.udm_log)
    write_csv(args.out_dir / "e6_native_timings_raw.csv", raw)
    summary = summarize(raw)
    write_csv(args.out_dir / "e6_native_timings.csv", summary)
    for row in summary:
        print(row)


if __name__ == "__main__":
    main()
