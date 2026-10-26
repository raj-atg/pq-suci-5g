"""Data encapsulation shared by all protected schemes: AES-128-CTR then HMAC-SHA-256/64."""

from __future__ import annotations

import hmac
from hashlib import sha256

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from pqsuci.kdf import SessionKeys

MAC_TAG_LEN = 8  # 64-bit tag (TS 33.501 C.3.4)


class DeconcealError(Exception):
    """Raised when the MAC tag does not verify or the scheme output is malformed."""


def _aes_ctr(keys: SessionKeys, data: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(keys.enc_key), modes.CTR(keys.icb))
    ctx = cipher.encryptor()
    return ctx.update(data) + ctx.finalize()


def mac_tag(keys: SessionKeys, ciphertext: bytes) -> bytes:
    """HMAC-SHA-256 over the ciphertext, truncated to 64 bits."""
    return hmac.new(keys.mac_key, ciphertext, sha256).digest()[:MAC_TAG_LEN]


def seal(keys: SessionKeys, plaintext: bytes) -> bytes:
    """Return ciphertext || tag."""
    ct = _aes_ctr(keys, plaintext)
    return ct + mac_tag(keys, ct)


def open_sealed(keys: SessionKeys, sealed: bytes) -> bytes:
    """Verify the tag and decrypt `ciphertext || tag`. Raises DeconcealError on failure."""
    if len(sealed) < MAC_TAG_LEN:
        raise DeconcealError("scheme output too short")
    ct, tag = sealed[:-MAC_TAG_LEN], sealed[-MAC_TAG_LEN:]
    if not hmac.compare_digest(mac_tag(keys, ct), tag):
        raise DeconcealError("MAC tag mismatch")
    return _aes_ctr(keys, ct)
