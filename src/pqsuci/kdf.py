"""ANSI X9.63 key derivation (SHA-256) and the SUCI session key split."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

ENC_KEY_LEN = 16  # AES-128 key
ICB_LEN = 16  # AES-CTR initial counter block
MAC_KEY_LEN = 32  # HMAC-SHA-256 key
SESSION_KEY_LEN = ENC_KEY_LEN + ICB_LEN + MAC_KEY_LEN


def x963_kdf(shared_secret: bytes, shared_info: bytes, length: int) -> bytes:
    """Derive `length` bytes with ANSI X9.63 KDF using SHA-256.

    K = SHA256(Z || Counter || SharedInfo) for Counter = 1, 2, ... (32-bit big endian),
    concatenated and truncated to `length` bytes.
    """
    if length <= 0:
        raise ValueError("length must be positive")
    out = bytearray()
    counter = 1
    while len(out) < length:
        out += hashlib.sha256(shared_secret + counter.to_bytes(4, "big") + shared_info).digest()
        counter += 1
    return bytes(out[:length])


@dataclass(frozen=True)
class SessionKeys:
    """Keys for the SUCI DEM: AES-128-CTR key, initial counter block and HMAC key."""

    enc_key: bytes
    icb: bytes
    mac_key: bytes


def derive_session_keys(shared_secret: bytes, shared_info: bytes) -> SessionKeys:
    """Split X9.63 output into K_enc (16 B) || ICB (16 B) || K_mac (32 B), as in TS 33.501 C.3."""
    k = x963_kdf(shared_secret, shared_info, SESSION_KEY_LEN)
    return SessionKeys(
        enc_key=k[:ENC_KEY_LEN],
        icb=k[ENC_KEY_LEN : ENC_KEY_LEN + ICB_LEN],
        mac_key=k[ENC_KEY_LEN + ICB_LEN :],
    )
