"""Registry of protection schemes and high level SUPI <-> SUCI helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from pqsuci import ecies, kem_suci
from pqsuci.suci_format import NULL_SCHEME_ID, Suci, bcd_to_msin, msin_to_bcd

KeyGen = Callable[[], tuple[bytes, bytes]]
Conceal = Callable[[bytes, bytes], bytes]
Deconceal = Callable[[bytes, bytes], bytes]


@dataclass(frozen=True)
class Scheme:
    """A protection scheme. Keys are raw bytes; conceal/deconceal work on BCD plaintext."""

    name: str
    scheme_id: int  # protection scheme identifier carried in the SUCI (-1: benchmark only)
    keygen: KeyGen
    conceal: Conceal
    deconceal: Deconceal


def _null_keygen() -> tuple[bytes, bytes]:
    return b"", b""


SCHEMES: dict[str, Scheme] = {
    s.name: s
    for s in (
        Scheme("null", NULL_SCHEME_ID, _null_keygen, lambda _k, p: p, lambda _k, o: o),
        Scheme(
            "profile-a",
            1,
            ecies.profile_a_keygen,
            ecies.profile_a_conceal,
            ecies.profile_a_deconceal,
        ),
        Scheme(
            "profile-b",
            2,
            ecies.profile_b_keygen,
            ecies.profile_b_conceal,
            ecies.profile_b_deconceal,
        ),
        *(
            Scheme(
                name,
                sid,
                partial(kem_suci.kem_keygen, alg),
                partial(kem_suci.kem_conceal, alg=alg),
                partial(kem_suci.kem_deconceal, alg=alg),
            )
            for name, sid, alg in (
                ("mlkem512", -1, "ML-KEM-512"),
                ("mlkem768", 12, "ML-KEM-768"),
                ("mlkem1024", -1, "ML-KEM-1024"),
            )
        ),
        Scheme(
            "hybrid",
            13,
            kem_suci.hybrid_keygen,
            kem_suci.hybrid_conceal,
            kem_suci.hybrid_deconceal,
        ),
    )
}


def scheme_by_id(scheme_id: int) -> Scheme:
    """Look up a scheme by its protection scheme identifier."""
    for s in SCHEMES.values():
        if s.scheme_id == scheme_id:
            return s
    raise KeyError(f"unknown protection scheme id {scheme_id}")


def conceal_imsi(
    scheme: Scheme,
    hn_pub: bytes,
    imsi: str,
    mnc_len: int = 2,
    key_id: int = 0,
    routing_indicator: str = "0000",
) -> Suci:
    """Build a SUCI for an IMSI-based SUPI. Only the MSIN is concealed."""
    if scheme.scheme_id < 0:
        raise ValueError(f"{scheme.name} has no protection scheme id (benchmark only)")
    mcc, mnc, msin = imsi[:3], imsi[3 : 3 + mnc_len], imsi[3 + mnc_len :]
    if scheme.scheme_id == NULL_SCHEME_ID:
        return Suci(mcc, mnc, routing_indicator, 0, 0, msin)
    output = scheme.conceal(hn_pub, msin_to_bcd(msin))
    return Suci(mcc, mnc, routing_indicator, scheme.scheme_id, key_id, output.hex())


def deconceal_suci(suci: Suci, hn_priv: bytes) -> str:
    """SIDF: recover the IMSI from a SUCI. Raises DeconcealError on a bad MAC."""
    if suci.scheme_id == NULL_SCHEME_ID:
        return suci.mcc + suci.mnc + suci.scheme_output
    scheme = scheme_by_id(suci.scheme_id)
    plaintext = scheme.deconceal(hn_priv, suci.output_bytes)
    return suci.mcc + suci.mnc + bcd_to_msin(plaintext)
