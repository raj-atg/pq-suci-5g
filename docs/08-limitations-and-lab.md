# Limitations and a plan for a real 5G lab

## Limitations of this setup

- One laptop under WSL2 runs everything. Timings depend on that machine and vary between runs. This is why E1 is repeated 3 times (`results/processed/e1_repeatability.csv`).
- The radio is simulated. UERANSIM carries the radio link (RLS, its radio link simulation) over UDP on the loopback interface. There is no real RRC (Radio Resource Control) and no PHY (physical layer). The radio cost of a larger SUCI is only modelled, in E5, with the simple assumptions listed in [06-experiments.md](06-experiments.md).
- All network functions run on one host. There is no network delay between them.
- UE-side timings measure the UERANSIM implementation, not a USIM (the card) or a phone. Stock Profile A in UERANSIM uses the compact25519 library with a random seed that does not come from the operating system. Our Profile B uses OpenSSL. Scheme 12 uses liboqs. These differ in implementation, so the timings compare code paths and not schemes in the abstract.
- Storing a 1184-byte ML-KEM-768 public key on a USIM was not tested. Only the UE configuration file holds the key.
- The test UEs are stopped without deregistering. The Open5GS AUSF keeps one context per SUCI and its pool fills up in long runs. The core is restarted before each scheme in E4 for this reason (see `results/raw/e4/invalid_ausf_pool/README.md`).
- Scheme 13 (hybrid) exists only in the Python package. It is not in the C patches, so it has no end-to-end test.
- Only ML-KEM-768 is integrated end to end. ML-KEM-512 and ML-KEM-1024 are only benchmarked (E1, E2, E5).
- There is no formal security analysis. Schemes 12 and 13 are a research prototype, not standardized.
- AMF and UDM were tested in a single PLMN (public land mobile network). There is no roaming and no SEPP (security edge protection proxy).
- CPU use was measured for the UDM process only, not for the other network functions.

## Plan for a university 5G lab

The goal is to repeat the key measurements with a real gNB, real phones and programmable SIM cards that support SUCI. Phones and SIMs will not support scheme 12, so the post-quantum part is projected from simulator runs and lab radio data.

1. **Baseline registration.**
   - Register phones with SUCI null, Profile A and Profile B, using programmable SIMs that support SUCI calculation on the USIM or in the mobile equipment.
   - Capture NGAP on the core side (the gNB to AMF link).
   - Compute registration time with the same markers as E3. Use `experiments/parse_ngap.py` on the captures: InitialUEMessage as start, InitialContextSetupRequest as registered, PDUSessionResourceSetupRequest as session.
   - Repeat many times per scheme, at different times of day. Keep the core and gNB settings fixed.
2. **First uplink message size and RRC segmentation.**
   - Measure the size of the first uplink RRC message that carries the NAS Registration Request (RRCSetupComplete) for each scheme.
   - Check whether RRC segmentation is used. Do this at several signal conditions (near, far, indoor), recording the signal strength.
   - Use gNB logs or a radio-side capture, since the core only sees the NAS payload.
3. **Replace the E5 assumptions.**
   - From the gNB scheduler logs, take the real uplink grant sizes and MCS (modulation and coding scheme) for the first message.
   - Rerun the airtime estimate of `experiments/e5_models.py` with these values instead of the illustrative PRB and MCS choices.
4. **Post-quantum projection.**
   - Run scheme 12 with UERANSIM against the lab core, which runs the patched Open5GS. This gives core-side cost with a post-quantum SUCI.
   - Project the over-the-air cost by using the lab's measured uplink throughput and grant sizes for a first message of the scheme 12 size (see `results/processed/e2_sizes_computed.csv`).
   - State clearly that this is a projection. No phone or SIM was used for scheme 12.
5. **What to record.**
   - For every run: scheme, phone or SIM model, signal strength, time of day, core and gNB software versions and settings.
   - NGAP captures, gNB and core logs, scheduler logs, and the first uplink message size.
   - Timestamps from one synchronized clock for the gNB, the core and the capture host.
   - Failed registrations and retries, not only successful ones.
