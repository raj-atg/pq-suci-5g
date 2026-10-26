# 10. Deploying post-quantum SUCI in real networks

Can a post-quantum SUCI be used in real 5G networks, and what stands in the way? This document
combines what this project measured with the published state of standardization.

**Short answer.** Technically yes. Neither the cryptography nor the capacity of the core is the
problem. The blockers are the SIM cards and phones that must compute the SUCI, the need for a
standard that every network on a roaming path accepts, and many small hardcoded limits in
products. A private 5G network that controls its own SIMs, devices and core can deploy it today;
a public operator with roaming partners needs the standard first.

## 1. What is not a blocker (measured in this project)

| Concern | Result | Source |
|---|---|---|
| CPU on the UE side | ML-KEM-768 conceal 41.8 us vs 92.0 us for Profile A (Python) | `results/processed/e1_repeatability.csv` |
| CPU in the home network | Open5GS SIDF de-conceal 90.5 us vs 598.5 us (Profile A) and 1557.0 us (Profile B) | `results/processed/e6_native_timings.csv` |
| Core capacity under load | 100 simultaneous registrations: median 725.7 ms vs 805.7 ms (Profile A); UDM CPU per UE 4.07 vs 5.40 ms | `results/processed/summary.csv` |
| Message size limits in the protocols | a 1101-byte scheme output passed NAS (16-bit length field), NGAP and the HTTP/2 service interface (2226-character SUCI in the URI) | `results/processed/tier3_interop.csv`, [05](05-tier3-integration.md) |

This agrees with Ericsson's public statement that the SUCI protocol was designed to allow
ciphertexts and public keys of several thousand bytes (see References).

## 2. Blockers

### 2.1 SIM cards and devices

The SUCI is computed either on the USIM or by the phone (ME, mobile equipment), as configured by
the home operator.

- **Deployed hardware does not know the new scheme.** SIM cards and modem firmware support the
  schemes they shipped with (Profiles A and B). A new public-key algorithm generally needs new
  SIM applet or modem software, not only a new key.
- **Key size on the SIM.** The home network public key grows from 32 or 33 bytes to 1184 bytes
  (ML-KEM-768). The USIM stores a list of such keys, so operators that rotate keys need room for
  several.
- **Computation on the SIM.** SIM chips are small, low-power processors. Running ML-KEM there is
  a separate engineering question from running it on a laptop; Ulitzsch et al. (WiSec 2022)
  evaluated a KEM-based SUCI on constrained hardware.
- **Lifetime.** SIMs and devices stay in use for many years. The time to replace them sets the
  pace of migration more than anything else.
- **eSIM provisioning** uses its own public-key protocols, which also need a post-quantum update
  (see the 2026 IACR ePrint on post-quantum eSIM provisioning in the References).

### 2.2 Standardization and roaming

- **Proprietary scheme IDs only work end to end if every network in the path forwards them.**
  TS 23.003 reserves scheme IDs 12 to 15 for the home network, and conceptually the serving
  network only forwards the SUCI home. In practice, Open5GS's serving AMF rejected scheme ID 12
  (Registration Reject, cause 95) until it was patched in three places
  ([05](05-tier3-integration.md), items O1 to O3). If commercial AMFs behave the same way, a
  roaming subscriber with a proprietary scheme would be rejected by the visited network.
- **Elements between networks were not tested here.** In roaming, the SUCI also passes Security
  Edge Protection Proxies (SEPP) and possibly signaling firewalls, which may have their own
  message or URI length limits.
- **Standardization status (as published by 3GPP).** 3GPP SA3 has documented a cryptographic
  inventory for 5G standalone (TR 33.938) and runs a Release 20 study on transitioning to
  post-quantum cryptography (TR 33.703). The 3GPP page dated 29 July 2026 describes the study as
  ongoing with a target of June 2026, followed by work on normative specifications. The same
  page names GSMA PQ.03 and ETSI TC CYBER migration guidance as triggers, and says NIST
  algorithms are preferred. Until a normative SUCI profile exists, vendors have no common target
  to implement.

### 2.3 Radio cost for weak links

Scheme 12 adds about 1 kB to the first uplink NAS message. Under the model in
[06](06-experiments.md) this is up to 10 extra 0.5 ms slots for a UE with a 10 PRB QPSK grant,
and about one slot with larger grants (`results/processed/e5_airtime.csv`). The message may also
need RRC segmentation. This matters most where links are weak or slow: cell edge, low-power and
IoT devices, and non-terrestrial (satellite) access. These numbers are from a model, not from a
real radio; [08](08-limitations-and-lab.md) describes how to measure them.

The cost is paid only when a SUCI is actually sent. A UE that holds a valid 5G-GUTI (temporary
identity) registers with the GUTI instead, and a UE reuses the same SUCI while timer T3519 runs
(UERANSIM `src/ue/nas/mm/identity.cpp`, `getOrGeneratePreferredId` and `getOrGenerateSuci`). The
SUCI is mainly sent at initial registration and when the network asks for the identity.

### 2.4 Home network key management

- The SIDF private key is normally kept in a hardware security module (HSM). The HSM must support
  ML-KEM and the UDM must be integrated with it.
- Key identifiers allow several keys at once (Open5GS accepts identifiers 1 to 254,
  `lib/sbi/context.h:59-60`), so a new post-quantum key can be added next to the ECIES keys and
  SIMs can be moved over gradually.

### 2.5 Hardcoded limits in products

The fixes in this project were small, but they were spread over three components (UE, AMF, UDM)
and included an 8-bit size variable, a 32-byte key slot, a 69-byte KDF buffer and fixed scheme
lists ([05](05-tier3-integration.md)). Commercial cores, SIM applets and modems will have their
own equivalents. Each must be found and fixed, and interoperability between vendors must be tested.

## 3. Practical migration paths

| Path | Who | What is needed | Main limitation |
|---|---|---|---|
| Private network, proprietary scheme | campus, industrial or research 5G networks that issue their own SIMs | programmable SIMs or SUCI computed in a controlled device, a patched core (like this project) | no roaming; device support |
| Public network, hybrid scheme | operators during the transition | standardized hybrid profile (for example X25519 + ML-KEM), SIM and modem support | waits for the standard and the device cycle |
| Public network, post-quantum only | later stage | standardized profile, broad device support | same, plus confidence in ML-KEM alone |

Hybrids (section 3 of [03](03-pq-design.md)) cost little extra: 32 more bytes than scheme 12 and
one X25519 operation (`results/processed/e2_sizes_computed.csv`, `e1_repeatability.csv`). They
keep today's security if ML-KEM or an implementation of it turns out to be weak.

**Choice of parameter set.** ML-KEM-512, -768 and -1024 differ mostly in size: scheme outputs of
781, 1101 and 1581 bytes (`results/processed/e2_sizes_computed.csv`); compute times are close
(`e1_repeatability.csv`). ML-KEM-768 (NIST security category 3) was chosen here as the middle
option. A network that cares most about cell-edge uplink could consider ML-KEM-512; one that
follows guidance requiring category 5 would need ML-KEM-1024.

## 4. What SUCI does not solve

Post-quantum SUCI protects the permanent identity in the first registration message against
"harvest now, decrypt later". It does not fix other known 5G privacy weaknesses, such as
linkability attacks on 5G-AKA (Koutsos, IEEE EuroS&P 2019), and it does not change the symmetric
cryptography of 5G-AKA. 3GPP is separately specifying 256-bit symmetric algorithm sets
(TS 35.240 to 35.248, listed on the 3GPP page below).

## 5. Open questions

- How do commercial AMFs, SEPPs and signaling firewalls treat unknown scheme IDs and long SUCIs?
- What is the real over-the-air cost (RRC segmentation, retransmissions) at the cell edge?
- How fast is ML-KEM on current SIM hardware, and how much storage do key lists need?
- Which hybrid combination, if any, will the standard choose?

## References

- 3GPP, "Post Quantum Cryptography in 3GPP", https://www.3gpp.org/technologies/pqc-sa3
  (page dated 29 July 2026; TR 33.938, TR 33.703, TS 35.240 to 35.248).
- GSMA, PQ.03 "Post Quantum Cryptography: Guidelines for Telecom Use Cases", v2.0, October 2024,
  https://www.gsma.com/solutions-and-impact/technologies/security/post-quantum-cryptography-documents/
- Ericsson, "Quantum-safe networks", https://www.ericsson.com/en/security/quantum-safe-networks
- V. Q. Ulitzsch, S. Park, S. Marzougui, J.-P. Seifert, A post-quantum secure subscription
  concealed identifier for 6G, ACM WiSec 2022, DOI 10.1145/3507657.3528540.
- "Towards Post-Quantum Secure eSIM Provisioning Protocols", IACR ePrint 2026/1225,
  https://eprint.iacr.org/2026/1225
- A. Koutsos, The 5G-AKA authentication protocol privacy, IEEE EuroS&P 2019.
- NIST FIPS 203, Module-Lattice-Based Key-Encapsulation Mechanism Standard, 2024.
