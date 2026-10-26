"""E5: analytical models built on measured E1 times and computed E2 sizes.

(a) SIDF capacity: M/M/c queue (Erlang C). Mean service time S is the mean Python
    de-concealment time from E1. Mean response time W = Wq + S. The model ignores everything
    except de-concealment (no UDM/UDR/SBI/AUSF work, no network latency, no batching).
    The null scheme is excluded (no cryptography).

(b) Uplink airtime for the extra SUCI bytes, with deliberately simple assumptions:
    NR, 30 kHz SCS (0.5 ms slot), 1 layer, 14 OFDM symbols per slot of which 12 carry data
    (2 assumed for DMRS/control), 12 subcarriers per PRB, so
    bits_per_slot = PRB * 12 * 12 * Qm * R.
    No transport block size quantization, no MAC/RLC/PDCP headers, no HARQ retransmissions.
    PRB grants {10, 50, 273}. QPSK R=0.30, 16QAM R=0.50, 64QAM R=0.75 are illustrative
    mid-range MCS choices, not taken from a specific MCS table row.
    extra_slots = ceil(extra_bits / bits_per_slot); extra_time_ms = extra_slots * 0.5.
    Extra bytes are the scheme output size minus that of profile-a (or null).
    A zero or negative difference gives zero extra slots.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "results" / "processed"
SCHEMES = ("profile-a", "profile-b", "mlkem512", "mlkem768", "mlkem1024", "hybrid")
SERVERS = (1, 2, 4)
GRID_POINTS = 200
W_TARGET_MS = 10.0
SLOT_MS = 0.5
PRBS = (10, 50, 273)
MODULATIONS = (("QPSK", 2, 0.30), ("16QAM", 4, 0.50), ("64QAM", 6, 0.75))
SEED = 0

AIRTIME_NOTES = (
    "E5 airtime model assumptions\n"
    "NR, 30 kHz SCS (0.5 ms slot), 1 layer, 14 OFDM symbols per slot, 12 carry data\n"
    "(2 assumed for DMRS/control), 12 subcarriers per PRB:\n"
    "  bits_per_slot = PRB * 12 * 12 * Qm * R\n"
    "No TBS quantization, no MAC/RLC/PDCP headers, no HARQ retransmissions.\n"
    "PRB grants 10, 50, 273. QPSK R=0.30, 16QAM R=0.50, 64QAM R=0.75 are illustrative\n"
    "mid-range MCS choices.\n"
    "extra_bytes = scheme_output_bytes(scheme) - scheme_output_bytes(profile-a or null);\n"
    "extra_slots = ceil(extra_bits / bits_per_slot) (0 if not positive);\n"
    "extra_time_ms = extra_slots * 0.5.\n"
)


def erlang_c_wait(lam: float, s: float, c: int) -> float:
    """Return mean queueing delay Wq (seconds) of an M/M/c queue; requires lam*s/c < 1."""
    a = lam * s
    rho = a / c
    terms = [a**k / math.factorial(k) for k in range(c)]
    top = a**c / (math.factorial(c) * (1 - rho))
    p_wait = top / (sum(terms) + top)
    return p_wait * s / (c * (1 - rho))


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of dict rows."""
    with path.open() as f:
        return list(csv.DictReader(f))


def sidf_capacity() -> None:
    """Write the M/M/c capacity grid and saturation summary."""
    rows = read_csv(PROC / "e1_micro_python.csv")
    mean_us = {r["scheme"]: float(r["mean_us"]) for r in rows if r["operation"] == "deconceal"}
    with (
        (PROC / "e5_sidf_capacity.csv").open("w", newline="") as fc,
        (PROC / "e5_sidf_saturation.csv").open("w", newline="") as fs,
    ):
        wc, ws = csv.writer(fc), csv.writer(fs)
        wc.writerow(
            ["impl", "scheme", "c", "service_time_us", "arrival_rate_per_s", "utilization",
             "mean_response_ms"]
        )
        ws.writerow(
            ["impl", "scheme", "c", "service_time_us", "saturation_rate_per_s",
             "rate_at_W_eq_10ms_per_s"]
        )
        for scheme in SCHEMES:
            s = mean_us[scheme] * 1e-6
            for c in SERVERS:
                sat = c / s
                grid = np.geomspace(1.0, 0.99 * sat, GRID_POINTS)
                ok: list[float] = []
                for lam in grid:
                    w_ms = (erlang_c_wait(float(lam), s, c) + s) * 1e3
                    wc.writerow(["python", scheme, c, f"{s * 1e6:.3f}", f"{lam:.6g}",
                                 f"{lam * s / c:.6f}", f"{w_ms:.6f}"])
                    if w_ms <= W_TARGET_MS:
                        ok.append(float(lam))
                ws.writerow(["python", scheme, c, f"{s * 1e6:.3f}", f"{sat:.6g}",
                             f"{max(ok):.6g}" if ok else ""])


def airtime() -> None:
    """Write the extra uplink airtime per scheme, PRB grant and modulation."""
    size = {r["scheme"]: int(r["scheme_output_bytes"]) for r in read_csv(PROC / "e2_sizes_computed.csv")}
    with (PROC / "e5_airtime.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["scheme", "extra_bytes_vs_profile_a", "extra_bytes_vs_null", "prbs", "modulation",
             "qm", "code_rate", "bits_per_slot", "extra_slots_vs_profile_a",
             "extra_time_ms_vs_profile_a", "extra_slots_vs_null", "extra_time_ms_vs_null"]
        )
        for scheme in SCHEMES:
            xa, xn = size[scheme] - size["profile-a"], size[scheme] - size["null"]
            for prbs in PRBS:
                for mod, qm, rate in MODULATIONS:
                    bps = prbs * 12 * 12 * qm * rate
                    sa = max(0, math.ceil(xa * 8 / bps))
                    sn = max(0, math.ceil(xn * 8 / bps))
                    w.writerow([scheme, xa, xn, prbs, mod, qm, rate, f"{bps:.1f}", sa,
                                f"{sa * SLOT_MS:.1f}", sn, f"{sn * SLOT_MS:.1f}"])
    (PROC / "e5_airtime_notes.txt").write_text(AIRTIME_NOTES)


def main() -> None:
    """Run both models. The grid is deterministic; no randomness is used."""
    np.random.seed(SEED)
    sidf_capacity()
    if (PROC / "e2_sizes_computed.csv").exists():
        airtime()


if __name__ == "__main__":
    main()
