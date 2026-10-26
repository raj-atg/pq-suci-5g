#!/usr/bin/env bash
# Generate TEST ONLY home network key pairs into config/keys/ (skips files that already exist).
#   id 1: Profile A (X25519)       curve25519-1.key (PEM, used by Open5GS) + .priv.hex/.pub.hex
#   id 2: Profile B (secp256r1)    secp256r1-2.key  (PEM, used by Open5GS) + .priv.hex/.pub.hex
#   id 3: scheme 12 (ML-KEM-768)   mlkem768-3.priv.hex / .pub.hex
#   id 4: scheme 13 (X25519 + ML-KEM-768) hybrid-4.priv.hex / .pub.hex
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEYS="$ROOT/config/keys"
PY="$ROOT/.venv/bin/python"
export OQS_INSTALL_PATH="${OQS_INSTALL_PATH:-$ROOT/third_party/install/liboqs}"
mkdir -p "$KEYS"
cd "$KEYS"

[[ -f curve25519-1.key ]] || openssl genpkey -algorithm X25519 -out curve25519-1.key
[[ -f secp256r1-2.key ]] || openssl ecparam -name prime256v1 -genkey -conv_form compressed -out secp256r1-2.key

# Raw hex forms of the PEM keys (for UERANSIM configs and the Python SIDF).
"$PY" - <<'PY'
from pathlib import Path

from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric import ec

for pem, stem in (("curve25519-1.key", "profile-a-1"), ("secp256r1-2.key", "profile-b-2")):
    if Path(f"{stem}.pub.hex").exists():
        continue
    sk = s.load_pem_private_key(Path(pem).read_bytes(), password=None)
    if isinstance(sk, ec.EllipticCurvePrivateKey):
        priv = sk.private_numbers().private_value.to_bytes(32, "big")
        pub = sk.public_key().public_bytes(s.Encoding.X962, s.PublicFormat.CompressedPoint)
    else:
        priv = sk.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
        pub = sk.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
    Path(f"{stem}.priv.hex").write_text(priv.hex() + "\n")
    Path(f"{stem}.pub.hex").write_text(pub.hex() + "\n")
PY

[[ -f mlkem768-3.pub.hex ]] || "$ROOT/.venv/bin/pqsuci" keygen --scheme mlkem768 --out mlkem768-3
[[ -f hybrid-4.pub.hex ]] || "$ROOT/.venv/bin/pqsuci" keygen --scheme hybrid --out hybrid-4

# ML-KEM secret key also as raw binary for the patched Open5GS UDM.
[[ -f mlkem768-3.priv.bin ]] || xxd -r -p mlkem768-3.priv.hex > mlkem768-3.priv.bin
echo "test keys in $KEYS"
