# 05. Post-quantum SUCI on the real core: changes and limits found

This document lists what had to change in Open5GS v2.8.0 and UERANSIM v3.3.0 so that a UE can
register with SUCI protection scheme 12 (ML-KEM-768), and every fixed-size limit or hardcoded
assumption found on the way. Line numbers refer to the unmodified upstream tags.

**Outcome: success.** A UE registered with scheme 12, the capture shows protection scheme ID 12,
the UDM log shows the SUPI recovered by the SIDF, the PDU session was established and a ping went
through the user-plane tunnel. Details and evidence are in [Outcome](#outcome).

The patches are in `patches/` and are applied by `scripts/apply_patches.sh` into separate
worktrees (`third_party/open5gs-pq`, `third_party/UERANSIM-pq`). The stock builds stay untouched
and are used for the baseline.

## 1. Limit audit

"Blocks scheme 12" means registration fails or the process aborts without a change.

### UERANSIM v3.3.0 (UE side)

| # | Location | What it assumes | Effect on scheme 12 | Fix |
|---|---|---|---|---|
| U1 | `src/ue/nas/mm/identity.cpp:113-122` (`generateSuci`) | only schemes 0 and 1 exist | blocks: "Protection Scheme 12 not implemented" (also blocks Profile B) | new branches for schemes 2 and 12 |
| U2 | `src/ue.cpp:158` | `homeNetworkPublicKey` is exactly 64 hex characters (32 bytes) | blocks: config is rejected for a 33-byte (Profile B) or 1184-byte (ML-KEM-768) key | allow 64 to 8192 hex characters |
| U3 | `src/ext/crypt-ext/x963kdf.c:34,41` | KDF shared secret and SharedInfo are both 32 bytes | would silently derive wrong keys with a 1088-byte SharedInfo | new KDF over OpenSSL EVP with any input length |
| U4 | `src/lib/rls/rls_pdu.cpp:118`, `src/ue/rls/udp_task.cpp:19` | radio simulation PDUs up to 16384 bytes | no effect (the Registration Request is far smaller) | none |
| U5 | `src/lib/nas/ie6.cpp` (5GS mobile identity encoding) | scheme output is opaque hex | no effect | none |

Observation (no change made): the stock Profile A code seeds its ephemeral key from
`Random::Mixed("Seed for x25519 generation")` in `identity.cpp`, not from an OS random source.

### Open5GS v2.8.0 (network side)

| # | Location | What it assumes | Effect on scheme 12 | Fix |
|---|---|---|---|---|
| O1 | `src/amf/gmm-handler.c:159-163` (`gmm_handle_registration_request`) | scheme ID is 0, 1 or 2 | blocks: Registration Reject, 5GMM cause 95 (semantically incorrect message) | add scheme 12 |
| O2 | `src/amf/context.c:1911-1916` (`amf_ue_find_by_message`) | same | blocks: "Invalid ProtectionSchemeID(12) in SUCI" | add scheme 12 |
| O3 | `src/amf/gmm-handler.c:1057-1061` (`gmm_handle_identity_response`) | same | blocks the Identity Response path | add scheme 12 |
| O4 | `lib/nas/5gs/conv.c:94-99` (`ogs_nas_5gs_suci_from_mobile_identity`) | same | blocks building the SUCI string | add scheme 12 |
| O5 | `lib/sbi/conv.c:28` (`parse_scheme_output`) | scheme output size stored in `uint8_t` | would wrap: 1101 bytes becomes 77 | scheme 12 uses its own parser with `size_t` |
| O6 | `lib/sbi/conv.c:52-64` | ephemeral key 32 or 33 bytes, ciphertext exactly 5 bytes (`OGS_MSIN_LEN`) | wrong split of the scheme output | own parser: 1088-byte ciphertext, rest is MSIN and tag |
| O7 | `lib/crypt/ogs-kdf.c:280,291` (`ogs_kdf_ansi_x963`) | `z_len + 4 + info_len <= 69` bytes, enforced by `ogs_assert` | would abort the UDM process (SharedInfo is 1088 bytes) | new streaming X9.63 KDF (`pq_kdf_ansi_x963`) |
| O8 | `lib/sbi/context.h:65` | `hnet[].key` is `uint8_t[32]` | cannot hold the 2400-byte ML-KEM secret key | add heap pointer `pq_key` and `pq_key_len` |
| O9 | `lib/sbi/context.c:692` (`ogs_sbi_context_parse_hnet_config`) | `scheme` is 1 or 2 | key is not loaded | accept 12, load a raw binary key file |
| O10 | `lib/nas/5gs/types.h:254` | 5GS mobile identity length is `uint16_t` | no effect (1109 bytes fits) | none |
| O11 | SBI (HTTP/2) path with the SUCI in the URI | none found | no effect: a 2226-character SUCI passed AMF to AUSF to UDM | none |

Also found: `src/udm/context.c:181` and `src/udm/udm-sm.c:183` both call
`ogs_supi_from_supi_or_suci()`, so the UDM can de-conceal the same SUCI more than once per
registration. The measured count per registration is in [07-results-and-discussion.md](07-results-and-discussion.md).

## 2. What the patches add

### UERANSIM (`patches/ueransim-v3.3.0-pq-suci.patch`)

- Profile B with OpenSSL 3: ephemeral P-256 key, ECDH with the 33-byte compressed home network
  key, compressed ephemeral key in the output. (OpenSSL returns the uncompressed point; the patch
  compresses it as `02/03 || x`.)
- Scheme 12 with liboqs: `OQS_KEM_encaps` with ML-KEM-768, then the shared DEM
  (X9.63 SHA-256 KDF, AES-128-CTR, HMAC-SHA-256 truncated to 8 bytes).
- A timing log line per SUCI: `[SUCI] scheme=<id> output_bytes=<n> conceal_us=<t>` (also added
  for Profile A, so all schemes are timed the same way).
- Links the UE library with `OpenSSL::Crypto` and liboqs (pkg-config).

### Open5GS (`patches/open5gs-v2.8.0-pq-suci.patch`)

- `OGS_PROTECTION_SCHEME_PQ_MLKEM768 = 12` (`lib/proto/types.h`).
- AMF and NAS accept-lists (O1 to O4).
- `hnet` entries with `scheme: 12` load a raw 2400-byte ML-KEM-768 secret key file.
- SIDF: `pq_mlkem768_supi_from_suci()` in `lib/sbi/conv.c`: hex decode, `OQS_KEM_decaps`, new
  KDF, constant-time tag comparison, AES-128-CTR, BCD decode.
- A timing wrapper around every de-concealment:
  `[SIDF] scheme=<id> suci_len=<n> supi=<supi> deconceal_us=<t>`.
- Links `libogssbi` with liboqs (meson `dependency('liboqs')`).

Config: `config/open5gs/udm-pq.yaml` adds `hnet` key ID 3 with scheme 12. UE config:
`config/ueransim/ue-pq.yaml` (`protectionScheme: 12`, `homeNetworkPublicKeyId: 3`, the 1184-byte
public key).

## 3. Outcome

Evidence (all from the run that produced `results/raw/tier3/`):

| Check | Evidence |
|---|---|
| UE computed a scheme 12 SUCI | `results/raw/tier3/pq.ue.log`: `[SUCI] scheme=12 output_bytes=1101` |
| Capture shows scheme ID 12 | `results/raw/pcap_samples/tier3_scheme12.pcap`, Wireshark: "Protection scheme Id: Unknown (12)", 5GS mobile identity length 1109 |
| SUCI crossed the SBI | 2226-character SUCI in `/nudm-ueau/v1/<suci>/security-information/generate-auth-data` (`results/processed/tier3_interop.csv`) |
| SIDF recovered the SUPI | UDM log: `[SIDF] scheme=12 suci_len=2226 supi=imsi-999700000000001` |
| Independent check | the captured SUCI de-conceals to `999700000000001` with the Python implementation (`results/processed/tier3_interop.csv`, `match=True`) |
| PDU session and user plane | `results/raw/tier3/pq.status`: `sessions_ok=1/1 success=1 ping=ok` |

The same table holds for Profile B, which also needed the UERANSIM patch (U1, U2).

### Debugging notes

- First scheme 12 attempt: AMF rejected with cause 95 (O1, O2). The NAS and SIDF changes alone
  were not enough; the serving AMF validated the scheme ID itself.
- First Profile B attempt: `EVP_PKEY_get_octet_string_param` with the "compressed" format
  setting still required a 65-byte buffer. Fixed by compressing manually.

## 4. What this means

A home network cannot deploy a proprietary SUCI scheme on this core by changing only the UDM.
Open5GS checks the scheme ID in the serving AMF too, so a visited network running this code would
reject such a UE. In terms of transport, nothing in NAS, NGAP, the simulated radio or the SBI
HTTP/2 path limited a SUCI of about 1.1 kB on the wire and 2.2 kB as text.
