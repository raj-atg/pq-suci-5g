"""E2 (computed part): key, scheme output, SUCI string and NAS identity sizes per scheme.

NAS 5GS mobile identity size (nas_mobile_identity_bytes), as an IEI-less LV-E:
    2 length octets + 8 SUCI header octets + scheme output bytes
where the 8 header octets are: identity type/SUPI format (1), MCC/MNC (3),
routing indicator (2), protection scheme id (1), home network public key id (1).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

os.environ.setdefault(
    "OQS_INSTALL_PATH",
    str(Path(__file__).resolve().parents[1] / "third_party" / "install" / "liboqs"),
)

from pqsuci.schemes import SCHEMES, Scheme, conceal_imsi  # noqa: E402
from pqsuci.suci_format import Suci, msin_to_bcd  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "results" / "processed"
IMSI = "999700000000001"
MSIN = "0000000001"
PLACEHOLDER_ID = 12
LV_E_LENGTH_OCTETS = 2
SUCI_HEADER_OCTETS = 8

NOTES = """E2 computed sizes: notes
hn_public_key_bytes: length of the public key from the scheme keygen (null: 0).
scheme_output_bytes: length of conceal output for a 10-digit MSIN (null: 5 bytes BCD).
suci_string_chars: len(conceal_imsi(IMSI 999700000000001, mnc_len=2, key_id=1).to_string()).
  mlkem512 and mlkem1024 have no scheme id (benchmark only): placeholder scheme id 12 is used
  to build the string, so only the length is an estimate (scheme_id column is -1).
nas_mobile_identity_bytes = 2 (LV-E length octets) + 8 (SUCI header: type 1, MCC/MNC 3,
  routing indicator 2, scheme id 1, key id 1) + scheme_output_bytes. No IEI octet.
"""


def suci_string(s: Scheme, pub: bytes) -> str:
    """Return the SUCI string, using a placeholder scheme id for benchmark-only schemes."""
    if s.scheme_id >= 0:
        return conceal_imsi(s, pub, IMSI, mnc_len=2, key_id=1).to_string()
    out = s.conceal(pub, msin_to_bcd(MSIN))
    return Suci(IMSI[:3], IMSI[3:5], "0000", PLACEHOLDER_ID, 1, out.hex()).to_string()


def main() -> None:
    """Compute sizes for every scheme and write the CSV and notes."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "e2_sizes_computed.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "scheme",
                "scheme_id",
                "hn_public_key_bytes",
                "scheme_output_bytes",
                "suci_string_chars",
                "nas_mobile_identity_bytes",
            ]
        )
        for name, s in SCHEMES.items():
            _priv, pub = s.keygen()
            out_len = len(s.conceal(pub, msin_to_bcd(MSIN)))
            w.writerow(
                [
                    name,
                    s.scheme_id,
                    len(pub),
                    out_len,
                    len(suci_string(s, pub)),
                    LV_E_LENGTH_OCTETS + SUCI_HEADER_OCTETS + out_len,
                ]
            )
    (OUT_DIR / "e2_sizes_notes.txt").write_text(NOTES)


if __name__ == "__main__":
    main()
