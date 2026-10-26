# TEST ONLY keys (generated locally, not committed)

`make keys` (`scripts/gen_test_keys.sh`) creates fresh **test** home network key pairs in this
folder, then `scripts/make_ue_configs.sh` writes the UERANSIM UE configs that contain the matching
public keys. The keys are gitignored and protect nothing real. Never use them in a real network or
on a real SIM.

| Key ID | Scheme | Files |
|---|---|---|
| 1 | Profile A (X25519) | `curve25519-1.key` (PEM, Open5GS), `profile-a-1.{priv,pub}.hex` |
| 2 | Profile B (secp256r1, compressed) | `secp256r1-2.key` (PEM, Open5GS), `profile-b-2.{priv,pub}.hex` |
| 3 | Scheme 12 (ML-KEM-768) | `mlkem768-3.{priv,pub}.hex`, `mlkem768-3.priv.bin` (raw, Open5GS) |
| 4 | Scheme 13 (X25519 + ML-KEM-768) | `hybrid-4.{priv,pub}.hex` |

The sample captures in `results/raw/pcap_samples/` were made with keys that are not published,
so their SUCIs cannot be de-concealed by others. To repeat the interoperability check, make new
captures with your own keys (`experiments/run_registration.sh`, then
`experiments/tier1_interop.py`).
