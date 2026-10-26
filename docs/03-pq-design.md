# 03. Post-quantum SUCI design

> **Research prototype.** Schemes 12 and 13 below are our own experiment. They are not part of
> any 3GPP specification. They use the protection scheme identifiers that TS 23.003 reserves for
> home network proprietary schemes (12 to 15), so they cannot clash with a standardized scheme.

## 1. Why identity privacy needs post-quantum protection

Today's SUCI protection (ECIES Profile A and B, see [02-suci-explained.md](02-suci-explained.md))
relies on elliptic curve Diffie-Hellman (ECDH). A large enough quantum computer running Shor's
algorithm could compute the elliptic curve private key from a public key, which breaks ECDH.

The attack that matters for identity privacy is **"harvest now, decrypt later"**:

1. Today, a passive attacker records radio traffic. Every initial Registration Request carries a
   SUCI, and the SUCI includes the UE's ephemeral public key.
2. Years later, the attacker gets a cryptographically relevant quantum computer.
3. The attacker recovers the ECDH shared secret from each recorded SUCI and decrypts the MSIN.
   The result is a list of "this permanent subscriber identity was at this place at this time".

The SUPI (Subscription Permanent Identifier) does not change for years, so location data that is
old is still personal data. That is why identity protection is a reasonable early candidate for
post-quantum migration, even before authentication keys are.

## 2. ML-KEM in one paragraph

ML-KEM (Module-Lattice-based Key Encapsulation Mechanism, standardized by NIST as FIPS 203,
derived from CRYSTALS-Kyber) is a **KEM**, not a Diffie-Hellman function. It has three operations:

- `KeyGen() -> (pk, sk)`: the home network does this once and puts `pk` in the USIM.
- `Encaps(pk) -> (ct, ss)`: the UE creates a fresh random shared secret `ss` (32 bytes) and a
  ciphertext `ct` that only the holder of `sk` can open.
- `Decaps(sk, ct) -> ss`: the SIDF recovers the same `ss`.

Its security rests on the Module Learning With Errors problem, for which no efficient quantum
attack is known. There are three parameter sets: ML-KEM-512, ML-KEM-768 and ML-KEM-1024
(NIST security categories 1, 3 and 5). The price is size: public keys and ciphertexts are around
a kilobyte instead of 32 or 33 bytes. The exact sizes we measured are in
`results/processed/e2_sizes_computed.csv`.

ML-KEM uses "implicit rejection": decapsulating a wrong or tampered ciphertext does not report an
error, it returns a pseudo-random secret. In our scheme the MAC check then fails, so tampering is
still detected.

## 3. ECIES is already a KEM-DEM, so the swap is small

ECIES in TS 33.501 Annex C can be read as two layers:

| Layer | ECIES Profile A | Our scheme 12 |
|---|---|---|
| KEM (agree on a secret) | ephemeral X25519 key pair, `Z = X25519(eph_sk, pk_HN)` | `(ct, ss) = ML-KEM-768.Encaps(pk_HN)` |
| What is sent for the KEM | ephemeral public key (32 B) | ML-KEM ciphertext `ct` |
| KDF | ANSI X9.63, SHA-256, SharedInfo = ephemeral public key | ANSI X9.63, SHA-256, SharedInfo = `ct` |
| DEM (encrypt MSIN) | AES-128-CTR, HMAC-SHA-256 tag truncated to 64 bits | identical |

So we keep the whole DEM (data encapsulation) from Annex C unchanged and only replace the KEM
(key encapsulation). This keeps the change easy to review and makes the cost difference come
almost entirely from ML-KEM.

### Scheme 12: ML-KEM-768

UE side (conceal):

```
(ct, ss)          = ML-KEM-768.Encaps(pk_HN)
K                 = X963-KDF-SHA256(Z = ss, SharedInfo = ct, 64 bytes)
K_enc || ICB || K_mac = K[0:16] || K[16:32] || K[32:64]
C                 = AES-128-CTR(K_enc, ICB, BCD(MSIN))
T                 = HMAC-SHA-256(K_mac, C)[0:8]
scheme output     = ct || C || T
```

Network side (SIDF, de-conceal): split the output, `ss = Decaps(sk_HN, ct)`, derive the same keys,
check `T` in constant time, then decrypt `C`. A wrong key or any changed byte makes the MAC check
fail.

Why SharedInfo = `ct`: in ECIES the ephemeral public key is bound into the KDF; the ML-KEM
ciphertext plays the same role. ML-KEM already binds `ct` into `ss`, so this is defense in depth
and keeps the structure parallel to Annex C.

### Scheme 13: hybrid X25519 + ML-KEM-768 (stretch goal)

```
eph_sk, eph_pub   = X25519 key pair (fresh)
Z_ec              = X25519(eph_sk, pk_HN_x25519)
(ct, ss)          = ML-KEM-768.Encaps(pk_HN_mlkem)
K                 = X963-KDF-SHA256(Z = Z_ec || ss, SharedInfo = eph_pub || ct, 64 bytes)
scheme output     = eph_pub || ct || AES-128-CTR(MSIN) || T
```

The home network public key is `pk_x25519 || pk_mlkem`.

**Why hybrids during the transition.** ML-KEM is young compared to elliptic curve cryptography.
A hybrid is secure if *either* component is secure: if a flaw is found in ML-KEM (or in an
implementation of it), the X25519 part still gives today's security; if a quantum computer
appears, the ML-KEM part still protects. The cost is 32 more bytes and one X25519 operation on
each side. Many transition plans for other protocols use hybrids for this reason.

## 4. Why the proprietary scheme ID range

The protection scheme identifier is a 4-bit field in the SUCI. Values 1 and 2 are the two
standardized ECIES profiles, values 3 to 11 are reserved for future standardized schemes, and
12 to 15 are for home network proprietary schemes (TS 23.003). The home network chooses both the
USIM content and the SIDF, so it can deploy a proprietary scheme without the serving network
understanding it: the serving AMF only needs to forward the SUCI to the home AUSF/UDM. Our
Tier 3 results show whether a real core actually behaves that way
(see [05-tier3-integration.md](05-tier3-integration.md)).

## 5. What this design does not cover

- It is not standardized and has not had any formal security analysis.
- We do not address the size of the USIM file that stores the home network public key (an
  ML-KEM-768 public key is much larger than an X25519 key).
- We protect identity privacy only. 5G-AKA authentication and key agreement are symmetric-key
  based and are not changed.
- Constant-time behaviour of the C code paths is inherited from liboqs and OpenSSL; we did not
  audit it.
