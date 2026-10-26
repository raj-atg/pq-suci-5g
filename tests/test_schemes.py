"""Tests for every protection scheme and the SUPI <-> SUCI helpers."""

import pytest

from pqsuci.dem import DeconcealError
from pqsuci.kem_suci import kem_details
from pqsuci.schemes import SCHEMES, Scheme, conceal_imsi, deconceal_suci, scheme_by_id
from pqsuci.suci_format import msin_to_bcd

PT = msin_to_bcd("0000000001")
ALL = sorted(SCHEMES)
PROTECTED = [n for n in ALL if n != "null"]
SIDED = [n for n in ALL if SCHEMES[n].scheme_id >= 0]
KEM_ALGS = {"mlkem512": "ML-KEM-512", "mlkem768": "ML-KEM-768", "mlkem1024": "ML-KEM-1024"}


def _expected_len(name: str, pt_len: int) -> int:
    if name == "profile-a":
        return 32 + pt_len + 8
    if name == "profile-b":
        return 33 + pt_len + 8
    if name == "hybrid":
        return 32 + 1088 + pt_len + 8
    return kem_details(KEM_ALGS[name])["ciphertext"] + pt_len + 8


@pytest.fixture(scope="module")
def keys() -> dict[str, tuple[bytes, bytes]]:
    return {n: SCHEMES[n].keygen() for n in ALL}


@pytest.mark.parametrize("name", ALL)
def test_round_trip(name: str, keys: dict[str, tuple[bytes, bytes]]) -> None:
    priv, pub = keys[name]
    s = SCHEMES[name]
    assert s.deconceal(priv, s.conceal(pub, PT)) == PT


@pytest.mark.parametrize("name", PROTECTED)
@pytest.mark.parametrize("pt_len", [1, 5, 8])
def test_output_length(name: str, pt_len: int, keys: dict[str, tuple[bytes, bytes]]) -> None:
    out = SCHEMES[name].conceal(keys[name][1], bytes(pt_len))
    assert len(out) == _expected_len(name, pt_len)


@pytest.mark.parametrize("name", PROTECTED)
def test_tampered_mac_rejected(name: str, keys: dict[str, tuple[bytes, bytes]]) -> None:
    priv, pub = keys[name]
    s = SCHEMES[name]
    out = bytearray(s.conceal(pub, PT))
    out[-1] ^= 0x01
    with pytest.raises(DeconcealError):
        s.deconceal(priv, bytes(out))


@pytest.mark.parametrize("name", PROTECTED)
def test_tampered_ciphertext_rejected(name: str, keys: dict[str, tuple[bytes, bytes]]) -> None:
    priv, pub = keys[name]
    s = SCHEMES[name]
    out = bytearray(s.conceal(pub, PT))
    out[-9] ^= 0x01  # last ciphertext byte, just before the 8 byte tag
    with pytest.raises(DeconcealError):
        s.deconceal(priv, bytes(out))


@pytest.mark.parametrize("name", PROTECTED)
def test_wrong_private_key_rejected(name: str, keys: dict[str, tuple[bytes, bytes]]) -> None:
    s = SCHEMES[name]
    other_priv, _ = s.keygen()
    with pytest.raises(DeconcealError):
        s.deconceal(other_priv, s.conceal(keys[name][1], PT))


@pytest.mark.parametrize("name", PROTECTED)
def test_truncated_output_rejected(name: str, keys: dict[str, tuple[bytes, bytes]]) -> None:
    priv, pub = keys[name]
    s = SCHEMES[name]
    out = s.conceal(pub, PT)
    for cut in (1, len(out) // 2, len(out) - 4, len(out)):
        with pytest.raises(DeconcealError):
            s.deconceal(priv, out[: len(out) - cut])


@pytest.mark.parametrize("name", PROTECTED)
def test_fresh_randomness(name: str, keys: dict[str, tuple[bytes, bytes]]) -> None:
    s = SCHEMES[name]
    pub = keys[name][1]
    assert s.conceal(pub, PT) != s.conceal(pub, PT)


@pytest.mark.parametrize("name", SIDED)
@pytest.mark.parametrize(("imsi", "mnc_len"), [("999700000000001", 2), ("310260123456789", 3)])
def test_imsi_round_trip(name: str, imsi: str, mnc_len: int, keys: dict) -> None:
    priv, pub = keys[name]
    s = SCHEMES[name]
    suci = conceal_imsi(s, pub, imsi, mnc_len=mnc_len)
    assert suci.scheme_id == s.scheme_id
    assert suci.mcc == imsi[:3]
    assert suci.mnc == imsi[3 : 3 + mnc_len]
    assert deconceal_suci(suci, priv) == imsi


@pytest.mark.parametrize("name", [n for n in ALL if SCHEMES[n].scheme_id < 0])
def test_benchmark_only_scheme_cannot_build_suci(name: str) -> None:
    s: Scheme = SCHEMES[name]
    with pytest.raises(ValueError):
        conceal_imsi(s, b"", "999700000000001")


def test_scheme_by_id() -> None:
    assert scheme_by_id(12).name == "mlkem768"
    assert scheme_by_id(13).name == "hybrid"
    assert scheme_by_id(1).name == "profile-a"
    assert scheme_by_id(2).name == "profile-b"
    assert scheme_by_id(0).name == "null"


@pytest.mark.parametrize("sid", [3, 11, 14, 99])
def test_scheme_by_id_unknown(sid: int) -> None:
    with pytest.raises(KeyError):
        scheme_by_id(sid)


def test_null_scheme_suci_string() -> None:
    suci = conceal_imsi(SCHEMES["null"], b"", "999700000000001", mnc_len=2)
    assert suci.to_string() == "suci-0-999-70-0000-0-0-0000000001"
    assert deconceal_suci(suci, b"") == "999700000000001"
