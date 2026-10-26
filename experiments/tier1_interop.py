"""Interoperability and privacy check on real captures.

For every capture given, extract the SUCI twice:
  1. from the NAS Registration Request (NGAP InitialUEMessage, procedure code 15), and
  2. from the SBI URI the AUSF sends to the UDM (`/nudm-ueau/v1/<suci>/...`),
then de-conceal it with the pqsuci Python SIDF using the TEST private keys, and compare the
result with the IMSI configured in the UE. Also saves the dissected 5GS mobile identity
(tshark -V) for the null vs protected comparison figure.

Usage: python experiments/tier1_interop.py results/raw/tier1/null.pcap ...
Output: results/processed/tier1_interop.csv, results/raw/tier1/<name>.mobile_identity.txt
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path

from pqsuci.dem import DeconcealError
from pqsuci.schemes import deconceal_suci
from pqsuci.suci_format import Suci, parse_suci

ROOT = Path(__file__).resolve().parents[1]
KEYS = ROOT / "config" / "keys"
PRIV_KEY_FILES = {
    0: None,
    1: "profile-a-1.priv.hex",
    2: "profile-b-2.priv.hex",
    12: "mlkem768-3.priv.hex",
    13: "hybrid-4.priv.hex",
}
EXPECTED_IMSI = "999700000000001"
NAS_FIELDS = [
    "nas-5gs.mm.suci.scheme_id",
    "nas-5gs.mm.suci.pki",
    "nas-5gs.mm.suci.scheme_output",
    "nas-5gs.mm.suci.msin",
]


def tshark_fields(pcap: Path, display_filter: str, fields: list[str]) -> list[list[str]]:
    """Run `tshark -T fields` and return rows of field values."""
    cmd = ["tshark", "-r", str(pcap), "-d", "tcp.port==7777,http2", "-Y", display_filter]
    cmd += ["-T", "fields", "-E", "separator=\t"]
    for f in fields:
        cmd += ["-e", f]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line.strip()]


def sbi_suci(pcap: Path) -> str | None:
    """Return the first SUCI string seen in an SBI request path."""
    rows = tshark_fields(pcap, 'http2.headers.path contains "suci-0"', ["http2.headers.path"])
    for (path,) in rows:
        match = re.search(r"(suci-0-[0-9a-fA-F-]+)", path)
        if match:
            return match.group(1)
    return None


def nas_identity(pcap: Path) -> dict[str, str]:
    """Return the SUCI fields of the first NAS Registration Request (InitialUEMessage)."""
    rows = tshark_fields(pcap, "ngap.procedureCode == 15 && nas-5gs.mm.suci.scheme_id", NAS_FIELDS)
    if not rows:
        return {}
    return dict(zip(NAS_FIELDS, rows[0] + [""] * (len(NAS_FIELDS) - len(rows[0])), strict=True))


def save_mobile_identity_text(pcap: Path) -> Path:
    """Save the dissected 5GS mobile identity block of the Registration Request."""
    out = subprocess.run(
        ["tshark", "-r", str(pcap), "-Y", "ngap.procedureCode == 15", "-V"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    lines = out.splitlines()
    start = next((i for i, line in enumerate(lines) if "5GS mobile identity" in line), None)
    block = [] if start is None else lines[start : start + 16]
    block = [line.strip() for line in block]
    dest = pcap.with_suffix(".mobile_identity.txt")
    dest.write_text("\n".join(block) + "\n")
    return dest


def deconceal(suci: Suci) -> tuple[str, str]:
    """De-conceal with the matching TEST key. Returns (imsi, status)."""
    key_file = PRIV_KEY_FILES.get(suci.scheme_id)
    priv = b"" if key_file is None else bytes.fromhex((KEYS / key_file).read_text().strip())
    try:
        return deconceal_suci(suci, priv), "ok"
    except (DeconcealError, KeyError, ValueError) as exc:
        return "", f"error: {exc}"


def check(pcap: Path) -> dict[str, object]:
    """Run the interop check for one capture."""
    nas = nas_identity(pcap)
    sbi = sbi_suci(pcap)
    row: dict[str, object] = {
        "capture": pcap.name,
        "nas_scheme_id": nas.get("nas-5gs.mm.suci.scheme_id", ""),
        "nas_pki": nas.get("nas-5gs.mm.suci.pki", ""),
        "nas_msin_in_clear": nas.get("nas-5gs.mm.suci.msin", ""),
        "nas_scheme_output_bytes": len(nas.get("nas-5gs.mm.suci.scheme_output", "")) // 2,
        "sbi_suci_chars": len(sbi) if sbi else 0,
        "sbi_suci": sbi or "",
    }
    if sbi:
        suci = parse_suci(sbi)
        imsi, status = deconceal(suci)
        row.update(recovered_imsi=imsi, status=status, match=imsi == EXPECTED_IMSI)
        nas_out = nas.get("nas-5gs.mm.suci.scheme_output", "").replace(":", "")
        row["nas_equals_sbi"] = suci.scheme_id == 0 or nas_out.lower() == suci.scheme_output
    else:
        row.update(recovered_imsi="", status="no SUCI in SBI", match=False, nas_equals_sbi=False)
    save_mobile_identity_text(pcap)
    return row


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcaps", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "results/processed/tier1_interop.csv")
    args = parser.parse_args()
    rows = [check(p) for p in args.pcaps]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        scheme, imsi = r["nas_scheme_id"], r["recovered_imsi"]
        print(f"{r['capture']}: scheme {scheme} -> {imsi} ({r['status']})")


if __name__ == "__main__":
    main()
