"""Post-quantum SUCI (research prototype, not standardized).

Scheme 12 (ML-KEM-768 KEM-DEM):
    (ct, ss) = ML-KEM.Encaps(pk_HN)
    keys     = X9.63-KDF(ss, SharedInfo = ct) -> K_enc || ICB || K_mac
    output   = ct || AES-128-CTR(MSIN) || HMAC-SHA-256/64 tag

Scheme 13 (hybrid X25519 + ML-KEM-768):
    Z = X25519(eph, pk_x) || ML-KEM ss,  SharedInfo = eph_pub || ct
    output = eph_pub || ct || AES-128-CTR(MSIN) || tag
    HN public key = pk_x (32 B) || pk_kem; HN private key = sk_x (32 B) || sk_kem.

ML-KEM-512 and ML-KEM-1024 use the same construction and are used for benchmarks only.
"""

from __future__ import annotations

from functools import cache

import oqs
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from pqsuci import dem
from pqsuci.kdf import derive_session_keys

ML_KEM_ALGS = ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024")
X25519_LEN = 32


@cache
def kem_details(alg: str) -> dict[str, int]:
    """Return liboqs size details for an ML-KEM parameter set."""
    if alg not in ML_KEM_ALGS:
        raise ValueError(f"unsupported KEM {alg}")
    with oqs.KeyEncapsulation(alg) as kem:
        d = kem.details
    return {
        "public_key": d["length_public_key"],
        "secret_key": d["length_secret_key"],
        "ciphertext": d["length_ciphertext"],
        "shared_secret": d["length_shared_secret"],
    }


def kem_keygen(alg: str = "ML-KEM-768") -> tuple[bytes, bytes]:
    """Return (secret key, public key) for an ML-KEM parameter set."""
    with oqs.KeyEncapsulation(alg) as kem:
        pk = kem.generate_keypair()
        return kem.export_secret_key(), pk


def kem_conceal(hn_pub: bytes, plaintext: bytes, alg: str = "ML-KEM-768") -> bytes:
    """UE side: KEM-DEM concealment."""
    with oqs.KeyEncapsulation(alg) as kem:
        ct, ss = kem.encap_secret(hn_pub)
    return ct + dem.seal(derive_session_keys(ss, ct), plaintext)


def kem_deconceal(hn_priv: bytes, output: bytes, alg: str = "ML-KEM-768") -> bytes:
    """Network side (SIDF): KEM-DEM de-concealment."""
    ct_len = kem_details(alg)["ciphertext"]
    if len(output) < ct_len + dem.MAC_TAG_LEN:
        raise dem.DeconcealError(f"{alg} output too short")
    ct, rest = output[:ct_len], output[ct_len:]
    with oqs.KeyEncapsulation(alg, secret_key=hn_priv) as kem:
        ss = kem.decap_secret(ct)
    return dem.open_sealed(derive_session_keys(ss, ct), rest)


def _x25519_pub(sk: x25519.X25519PrivateKey) -> bytes:
    return sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def hybrid_keygen(alg: str = "ML-KEM-768") -> tuple[bytes, bytes]:
    """Return (sk_x || sk_kem, pk_x || pk_kem)."""
    sk_x = x25519.X25519PrivateKey.generate()
    sk_x_raw = sk_x.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    sk_kem, pk_kem = kem_keygen(alg)
    return sk_x_raw + sk_kem, _x25519_pub(sk_x) + pk_kem


def hybrid_conceal(hn_pub: bytes, plaintext: bytes, alg: str = "ML-KEM-768") -> bytes:
    """UE side: hybrid X25519 + ML-KEM concealment."""
    pk_x, pk_kem = hn_pub[:X25519_LEN], hn_pub[X25519_LEN:]
    eph = x25519.X25519PrivateKey.generate()
    eph_pub = _x25519_pub(eph)
    z_ec = eph.exchange(x25519.X25519PublicKey.from_public_bytes(pk_x))
    with oqs.KeyEncapsulation(alg) as kem:
        ct, ss = kem.encap_secret(pk_kem)
    keys = derive_session_keys(z_ec + ss, eph_pub + ct)
    return eph_pub + ct + dem.seal(keys, plaintext)


def hybrid_deconceal(hn_priv: bytes, output: bytes, alg: str = "ML-KEM-768") -> bytes:
    """Network side (SIDF): hybrid de-concealment. Both secrets are needed."""
    ct_len = kem_details(alg)["ciphertext"]
    if len(output) < X25519_LEN + ct_len + dem.MAC_TAG_LEN:
        raise dem.DeconcealError("hybrid output too short")
    eph_pub = output[:X25519_LEN]
    ct = output[X25519_LEN : X25519_LEN + ct_len]
    rest = output[X25519_LEN + ct_len :]
    sk_x = x25519.X25519PrivateKey.from_private_bytes(hn_priv[:X25519_LEN])
    z_ec = sk_x.exchange(x25519.X25519PublicKey.from_public_bytes(eph_pub))
    with oqs.KeyEncapsulation(alg, secret_key=hn_priv[X25519_LEN:]) as kem:
        ss = kem.decap_secret(ct)
    keys = derive_session_keys(z_ec + ss, eph_pub + ct)
    return dem.open_sealed(keys, rest)
