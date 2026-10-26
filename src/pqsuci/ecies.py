"""ECIES Profile A (X25519) and Profile B (secp256r1, compressed point), TS 33.501 Annex C.

Scheme output = ephemeral public key || AES-128-CTR(plaintext) || HMAC-SHA-256/64 tag.
SharedInfo for the KDF is the ephemeral public key as transmitted.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, x25519

from pqsuci import dem
from pqsuci.kdf import derive_session_keys

X25519_PUB_LEN = 32
P256_COMPRESSED_LEN = 33

_RAW = serialization.Encoding.Raw
_RAW_PUB = serialization.PublicFormat.Raw
_RAW_PRIV = serialization.PrivateFormat.Raw
_NO_ENC = serialization.NoEncryption()


# Profile A ---------------------------------------------------------------------------------


def profile_a_keygen() -> tuple[bytes, bytes]:
    """Return (private key 32 B, public key 32 B) for X25519."""
    sk = x25519.X25519PrivateKey.generate()
    return sk.private_bytes(_RAW, _RAW_PRIV, _NO_ENC), sk.public_key().public_bytes(_RAW, _RAW_PUB)


def profile_a_conceal(hn_pub: bytes, plaintext: bytes) -> bytes:
    """UE side: ECIES Profile A concealment."""
    eph = x25519.X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes(_RAW, _RAW_PUB)
    z = eph.exchange(x25519.X25519PublicKey.from_public_bytes(hn_pub))
    return eph_pub + dem.seal(derive_session_keys(z, eph_pub), plaintext)


def profile_a_deconceal(hn_priv: bytes, output: bytes) -> bytes:
    """Network side (SIDF): ECIES Profile A de-concealment."""
    if len(output) < X25519_PUB_LEN + dem.MAC_TAG_LEN:
        raise dem.DeconcealError("Profile A output too short")
    eph_pub, rest = output[:X25519_PUB_LEN], output[X25519_PUB_LEN:]
    sk = x25519.X25519PrivateKey.from_private_bytes(hn_priv)
    z = sk.exchange(x25519.X25519PublicKey.from_public_bytes(eph_pub))
    return dem.open_sealed(derive_session_keys(z, eph_pub), rest)


# Profile B ---------------------------------------------------------------------------------


def _p256_private_from_bytes(raw: bytes) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def _p256_compressed(pub: ec.EllipticCurvePublicKey) -> bytes:
    return pub.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
    )


def profile_b_keygen() -> tuple[bytes, bytes]:
    """Return (private scalar 32 B, compressed public key 33 B) for secp256r1."""
    sk = ec.generate_private_key(ec.SECP256R1())
    priv = sk.private_numbers().private_value.to_bytes(32, "big")
    return priv, _p256_compressed(sk.public_key())


def profile_b_conceal(hn_pub: bytes, plaintext: bytes) -> bytes:
    """UE side: ECIES Profile B concealment (compressed ephemeral key)."""
    eph = ec.generate_private_key(ec.SECP256R1())
    eph_pub = _p256_compressed(eph.public_key())
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), hn_pub)
    z = eph.exchange(ec.ECDH(), peer)
    return eph_pub + dem.seal(derive_session_keys(z, eph_pub), plaintext)


def profile_b_deconceal(hn_priv: bytes, output: bytes) -> bytes:
    """Network side (SIDF): ECIES Profile B de-concealment."""
    if len(output) < P256_COMPRESSED_LEN + dem.MAC_TAG_LEN:
        raise dem.DeconcealError("Profile B output too short")
    eph_pub, rest = output[:P256_COMPRESSED_LEN], output[P256_COMPRESSED_LEN:]
    try:
        peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), eph_pub)
    except ValueError as exc:
        raise dem.DeconcealError("invalid ephemeral public key") from exc
    z = _p256_private_from_bytes(hn_priv).exchange(ec.ECDH(), peer)
    return dem.open_sealed(derive_session_keys(z, eph_pub), rest)
