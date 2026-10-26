"""Parse liboqs speed_kem output into a CSV (impl,scheme,operation,iterations,mean_us,cycles_mean)."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

SCHEME = {"ML-KEM-512": "mlkem512", "ML-KEM-768": "mlkem768", "ML-KEM-1024": "mlkem1024"}
OPS = {"keygen": "keygen", "encaps": "encaps", "decaps": "decaps"}


def split_cells(line: str) -> list[str]:
    """Split a table row on runs of two or more spaces or pipes."""
    return [c.strip() for c in re.split(r"\s*\|\s*|\s{2,}", line.strip()) if c.strip()]


def parse(text: str) -> list[list[str]]:
    """Return CSV rows from speed_kem stdout, using whichever columns are present."""
    rows: list[list[str]] = []
    header: list[str] = []
    scheme = ""
    for line in text.splitlines():
        cells = split_cells(line)
        if not cells:
            continue
        low = [c.lower() for c in cells]
        if "iterations" in low and any("mean" in c for c in low):
            header = low
            continue
        name = cells[0]
        if name in SCHEME:
            scheme = SCHEME[name]
            continue
        if header and scheme and name in OPS and len(cells) == len(header):
            rec = dict(zip(header, cells, strict=True))
            cyc = next((v for k, v in rec.items() if "cycles" in k and "mean" in k), "")
            mean = next(v for k, v in rec.items() if "mean" in k and "cycles" not in k)
            rows.append(["c-liboqs", scheme, OPS[name], rec["iterations"], mean, cyc])
    return rows


def main() -> None:
    """CLI: parse_speed_kem.py RAW_TXT OUT_CSV."""
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = parse(raw.read_text())
    if not rows:
        raise SystemExit("no rows parsed from speed_kem output")
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["impl", "scheme", "operation", "iterations", "mean_us", "cycles_mean"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
