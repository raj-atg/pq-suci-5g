"""Per-UE registration latency from NGAP markers in a capture (E3, E4, E6).

NGAP headers are not ciphered, so these markers are visible even when NAS is protected:
  start       InitialUEMessage                (procedureCode 15, initiatingMessage)
  registered  InitialContextSetupRequest      (procedureCode 14, initiatingMessage),
              carries the NAS Registration Accept in Open5GS
  session     PDUSessionResourceSetupRequest  (procedureCode 29, initiatingMessage)
UEs are correlated by RAN-UE-NGAP-ID (unique per gNB connection, one gNB per run).
Several NGAP PDUs can share one SCTP frame; tshark aggregates their values with '|'.

Usage: python experiments/parse_ngap.py --scheme profile-a --out CSV run1.pcap run2.pcap ...
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path

INITIATING = "0"
PROC_INITIAL_UE = "15"
PROC_ICS = "14"
PROC_PDU_SETUP = "29"
FIELDS = ["frame.time_epoch", "ngap.NGAP_PDU", "ngap.procedureCode", "ngap.RAN_UE_NGAP_ID"]


@dataclass
class UeTimes:
    """Marker timestamps (epoch seconds) and the Registration Request size for one UE."""

    start: float | None = None
    registered: float | None = None
    session: float | None = None
    nas_reg_request_bytes: int | None = None


def _split(value: str) -> list[str]:
    return value.split("|") if value else []


def ngap_rows(pcap: Path) -> list[list[str]]:
    """Return tshark field rows for all NGAP frames, NAS PDU hex last."""
    cmd = ["tshark", "-r", str(pcap), "-Y", "ngap", "-T", "fields", "-E", "aggregator=|"]
    for f in [*FIELDS, "ngap.NAS_PDU"]:
        cmd += ["-e", f]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line.strip()]


def ue_times(pcap: Path) -> dict[str, UeTimes]:
    """Collect the first occurrence of each marker per RAN-UE-NGAP-ID."""
    ues: dict[str, UeTimes] = {}
    for row in ngap_rows(pcap):
        row += [""] * (5 - len(row))
        t = float(row[0])
        pdus, procs, ids = _split(row[1]), _split(row[2]), _split(row[3])
        nas = _split(row[4])
        for i, (pdu, proc) in enumerate(zip(pdus, procs, strict=False)):
            if pdu != INITIATING or i >= len(ids):
                continue
            ue = ues.setdefault(ids[i], UeTimes())
            if proc == PROC_INITIAL_UE and ue.start is None:
                ue.start = t
                # InitialUEMessage carries exactly one NAS-PDU: the Registration Request.
                if nas:
                    ue.nas_reg_request_bytes = len(nas[min(i, len(nas) - 1)]) // 2
            elif proc == PROC_ICS and ue.registered is None:
                ue.registered = t
            elif proc == PROC_PDU_SETUP and ue.session is None:
                ue.session = t
    return ues


def _ms(a: float | None, b: float | None) -> str:
    return "" if a is None or b is None else f"{(b - a) * 1000:.3f}"


def rows_for(pcap: Path, scheme: str, core: str, n_ues: int, run: str) -> list[dict[str, str]]:
    """One CSV row per UE seen in the capture."""
    out = []
    for ran_id, ue in sorted(ue_times(pcap).items(), key=lambda kv: int(kv[0])):
        out.append(
            {
                "scheme": scheme,
                "core": core,
                "n_ues": str(n_ues),
                "run": run,
                "pcap": pcap.name,
                "ran_ue_ngap_id": ran_id,
                "nas_reg_request_bytes": str(ue.nas_reg_request_bytes or ""),
                "registration_ms": _ms(ue.start, ue.registered),
                "session_ms": _ms(ue.start, ue.session),
            }
        )
    return out


def main() -> None:
    """Entry point."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pcaps", nargs="+", type=Path)
    p.add_argument("--scheme", required=True)
    p.add_argument("--core", default="stock", help="stock or pq (patched build)")
    p.add_argument("--n-ues", type=int, default=1)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--append", action="store_true", help="append to an existing CSV")
    args = p.parse_args()

    rows = [
        r
        for pcap in args.pcaps
        for r in rows_for(pcap, args.scheme, args.core, args.n_ues, pcap.stem)
    ]
    mode = "a" if args.append and args.out.exists() else "w"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open(mode, newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "scheme",
                "core",
                "n_ues",
                "run",
                "pcap",
                "ran_ue_ngap_id",
                "nas_reg_request_bytes",
                "registration_ms",
                "session_ms",
            ],
        )
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} UE rows -> {args.out}")


if __name__ == "__main__":
    main()
