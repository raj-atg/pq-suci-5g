"""Tests for the X9.63 KDF and the session key split."""

import hashlib

import pytest

from pqsuci.kdf import SESSION_KEY_LEN, derive_session_keys, x963_kdf

Z = bytes(range(32))
INFO = b"shared-info-\x00\xff"


def _reference(z: bytes, info: bytes, length: int) -> bytes:
    blocks = -(-length // 32)
    out = b"".join(
        hashlib.sha256(z + i.to_bytes(4, "big") + info).digest() for i in range(1, blocks + 1)
    )
    return out[:length]


@pytest.mark.parametrize("length", [1, 16, 32, 33, 64, 100])
def test_x963_matches_independent_computation(length: int) -> None:
    assert x963_kdf(Z, INFO, length) == _reference(Z, INFO, length)


def test_x963_first_block_is_single_hash() -> None:
    expected = hashlib.sha256(Z + b"\x00\x00\x00\x01" + INFO).digest()
    assert x963_kdf(Z, INFO, 32) == expected


def test_x963_prefix_property() -> None:
    assert x963_kdf(Z, INFO, 100)[:40] == x963_kdf(Z, INFO, 40)


@pytest.mark.parametrize("length", [0, -1, -64])
def test_x963_rejects_non_positive_length(length: int) -> None:
    with pytest.raises(ValueError):
        x963_kdf(Z, INFO, length)


def test_derive_session_keys_split() -> None:
    keys = derive_session_keys(Z, INFO)
    assert (len(keys.enc_key), len(keys.icb), len(keys.mac_key)) == (16, 16, 32)
    assert keys.enc_key + keys.icb + keys.mac_key == _reference(Z, INFO, SESSION_KEY_LEN)
