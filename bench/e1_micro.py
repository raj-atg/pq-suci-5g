"""E1: Python microbenchmarks of SUCI protection schemes (keygen, conceal, deconceal)."""

from __future__ import annotations

import argparse
import csv
import gc
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

os.environ.setdefault("OQS_INSTALL_PATH", "~/pq-suci-5g/third_party/install/liboqs")

import oqs  # noqa: E402

from pqsuci.schemes import SCHEMES  # noqa: E402
from pqsuci.suci_format import msin_to_bcd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "results" / "raw" / "e1"
PROC_DIR = ROOT / "results" / "processed"
SCHEME_ORDER = ("null", "profile-a", "profile-b", "mlkem512", "mlkem768", "mlkem1024", "hybrid")
WARMUP = 200
PLAINTEXT = msin_to_bcd("0000000001")


def time_calls(fn: Callable[[int], object], n: int) -> list[int]:
    """Call fn(i) for i in range(n), returning per-call wall time in ns (GC disabled)."""
    out: list[int] = []
    gc.collect()
    gc.disable()
    try:
        for i in range(n):
            t0 = time.perf_counter_ns()
            fn(i)
            out.append(time.perf_counter_ns() - t0)
    finally:
        gc.enable()
    return out


def bench_scheme(name: str, n: int) -> dict[str, list[int]]:
    """Return per-iteration timings (ns) for keygen, conceal and deconceal of one scheme."""
    s = SCHEMES[name]
    for _ in range(WARMUP):
        s.keygen()
    keygen = time_calls(lambda _i: s.keygen(), n)

    priv, pub = s.keygen()
    for _ in range(WARMUP):
        s.deconceal(priv, s.conceal(pub, PLAINTEXT))
    conceal = time_calls(lambda _i: s.conceal(pub, PLAINTEXT), n)

    outputs = [s.conceal(pub, PLAINTEXT) for _ in range(n)]
    for o in outputs[:WARMUP]:
        s.deconceal(priv, o)
    deconceal = time_calls(lambda i: s.deconceal(priv, outputs[i]), n)
    return {"keygen": keygen, "conceal": conceal, "deconceal": deconceal}


def summarize(ns: list[int]) -> tuple[float, float, float, float]:
    """Return (median, p95, mean, std) in microseconds."""
    us = sorted(x / 1000 for x in ns)
    p95 = us[min(len(us) - 1, int(0.95 * len(us)))]
    return statistics.median(us), p95, statistics.fmean(us), statistics.stdev(us)


def sh(cmd: str) -> str:
    """Run a shell command and return stripped stdout (empty on failure)."""
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
    return res.stdout.strip()


def write_env(path: Path, pre_load: str) -> None:
    """Write environment details, including load recorded before the run started."""
    cpu_model = sh("lscpu").split("Model name:")[1].splitlines()[0].strip()
    lines = [
        f"cpu_model: {cpu_model}",
        f"nproc: {sh('nproc')}",
        f"kernel: {platform.release()}",
        f"python: {sys.version.split()[0]}",
        f"cryptography: {metadata.version('cryptography')}",
        f"liboqs-python: {metadata.version('liboqs-python')}",
        f"liboqs: {oqs.oqs_version()}",
        f"date_utc: {datetime.now(UTC).isoformat()}",
        f"command: {shlex.join([sys.executable, *sys.argv])}",
        "",
        pre_load,
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    """Run the benchmark and write raw and processed CSVs."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iterations", type=int, default=2000)
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    pre = (
        "uptime: "
        + sh("uptime")
        + "\nps top5 by cpu before run:\n"
        + sh("ps -eo comm,%cpu --sort=-%cpu | head -5")
    )
    write_env(RAW_DIR / "env.txt", pre)

    with (
        (RAW_DIR / "python_timings.csv").open("w", newline="") as raw,
        (PROC_DIR / "e1_micro_python.csv").open("w", newline="") as proc,
    ):
        rw, pw = csv.writer(raw), csv.writer(proc)
        rw.writerow(["scheme", "operation", "iteration", "ns"])
        pw.writerow(
            ["impl", "scheme", "operation", "n", "median_us", "p95_us", "mean_us", "std_us"]
        )
        for name in SCHEME_ORDER:
            for op, ns in bench_scheme(name, args.iterations).items():
                rw.writerows((name, op, i, v) for i, v in enumerate(ns))
                med, p95, mean, std = summarize(ns)
                pw.writerow(
                    [
                        "python",
                        name,
                        op,
                        len(ns),
                        f"{med:.3f}",
                        f"{p95:.3f}",
                        f"{mean:.3f}",
                        f"{std:.3f}",
                    ]
                )
                print(f"{name:10s} {op:10s} median {med:10.2f} us")


if __name__ == "__main__":
    main()
