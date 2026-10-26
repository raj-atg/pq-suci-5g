"""SUCI string format (TS 23.003 clause 2.2B) and MSIN BCD encoding.

suci-0-<MCC>-<MNC>-<RoutingIndicator>-<ProtectionSchemeId>-<HNPublicKeyId>-<SchemeOutput>
For the null scheme the scheme output is the MSIN digits; otherwise it is lowercase hex.
"""

from __future__ import annotations

from dataclasses import dataclass

NULL_SCHEME_ID = 0


def msin_to_bcd(msin: str) -> bytes:
    """Encode MSIN digits as swapped-nibble BCD (TBCD), padding an odd length with 0xF."""
    if not msin.isdigit():
        raise ValueError(f"MSIN must be digits: {msin!r}")
    digits = msin + ("F" if len(msin) % 2 else "")
    return bytes(int(digits[i + 1] + digits[i], 16) for i in range(0, len(digits), 2))


def bcd_to_msin(data: bytes) -> str:
    """Decode swapped-nibble BCD back to MSIN digits, dropping a 0xF filler."""
    out = []
    for b in data:
        out.append(f"{b & 0x0F:x}")
        out.append(f"{b >> 4:x}")
    s = "".join(out)
    if s.endswith("f"):
        s = s[:-1]
    if not s.isdigit():
        raise ValueError("invalid BCD MSIN")
    return s


@dataclass(frozen=True)
class Suci:
    """A parsed SUCI. `scheme_output` holds MSIN digits (null scheme) or hex text."""

    mcc: str
    mnc: str
    routing_indicator: str
    scheme_id: int
    key_id: int
    scheme_output: str

    def to_string(self) -> str:
        """Render the TS 23.003 NAI-like string used in SBI URIs."""
        return (
            f"suci-0-{self.mcc}-{self.mnc}-{self.routing_indicator}-"
            f"{self.scheme_id}-{self.key_id}-{self.scheme_output}"
        )

    @property
    def output_bytes(self) -> bytes:
        """Scheme output as raw bytes (BCD for the null scheme)."""
        if self.scheme_id == NULL_SCHEME_ID:
            return msin_to_bcd(self.scheme_output)
        return bytes.fromhex(self.scheme_output)


def parse_suci(text: str) -> Suci:
    """Parse `suci-0-...`. Only SUPI type 0 (IMSI) is supported."""
    parts = text.strip().split("-")
    if len(parts) != 8 or parts[0] != "suci":
        raise ValueError(f"not a SUCI string: {text!r}")
    if parts[1] != "0":
        raise ValueError("only SUPI type 0 (IMSI) is supported")
    mcc, mnc, ri = parts[2], parts[3], parts[4]
    if not (len(mcc) == 3 and mcc.isdigit() and len(mnc) in (2, 3) and mnc.isdigit()):
        raise ValueError("invalid MCC or MNC")
    return Suci(mcc, mnc, ri, int(parts[5]), int(parts[6]), parts[7])
