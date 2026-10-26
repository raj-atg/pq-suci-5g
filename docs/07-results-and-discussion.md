# 07. Results and discussion

All numbers below are copied from files in `results/processed/`. The headline values per scheme
are collected in `results/processed/summary.csv` (column sources in `summary_notes.txt`).
Method: [06-experiments.md](06-experiments.md). Hardware: Intel Core i3-1005G1, 4 vCPU,
3.7 GiB RAM, Ubuntu 26.04 on WSL2 (`results/raw/e1/env.txt`).

Short answer: on this setup, post-quantum SUCI (scheme 12, ML-KEM-768) costs bytes, not time.
The SUCI is about 24 times larger, but conceal and de-conceal are not slower than ECIES, a real
5G core registers the UE once the implementation limits are fixed, and registration latency and
UDM CPU under load are not worse than with Profile A or B.

## Figures

### Figure 1: SUCI size per scheme

![Figure 1](../results/figures/fig1_sizes.png)

Scheme output grows from 45 bytes (Profile A) and 46 bytes (Profile B) to 1101 bytes for scheme 12
and 1133 bytes for the hybrid scheme 13. The SUCI string carried in the SBI URI grows from 113 to
2226 characters (`e2_sizes_computed.csv`). On the wire, the NAS Registration Request grew from 65
bytes (Profile A) to 1121 bytes (scheme 12) (`summary.csv`, from `e3_registration.csv`).

### Figure 2: compute time

![Figure 2](../results/figures/fig2_compute.png)

- Python, median of three run medians (`e1_repeatability.csv`): conceal 92.0 us (Profile A),
  142.7 us (Profile B), 41.8 us (ML-KEM-768); de-conceal 88.4 us, 149.1 us and 44.4 us. The three
  runs agreed closely (min and max medians in the same file), except one outlier run for Profile A
  conceal (161.8 us max).
- Native liboqs (`e1_native_liboqs.csv`): ML-KEM-768 keygen 10.9 us, encaps 9.8 us, decaps 12.0 us.
- Inside the real stack (`e6_native_timings.csv`): the Open5GS SIDF needed a median of 598.5 us
  (Profile A), 1557.0 us (Profile B) and 90.5 us (scheme 12). Open5GS uses its own portable
  elliptic curve code, while liboqs uses AVX2-optimized ML-KEM, which explains most of the gap.
- UE side inside UERANSIM: medians 7136.1 us (Profile A), 2286.6 us (Profile B), 1857.2 us
  (scheme 12), with long tails (p95 up to tens of milliseconds, same file). These measure the
  simulator's implementations, not a USIM. The stock Profile A code uses a small portable X25519
  library and a slow seeding step, so it should not be read as "ECIES costs 7 ms".

### Figure 3: single-UE registration latency (E3)

![Figure 3](../results/figures/fig3_registration_latency.png)

30 runs per scheme on the patched core (`e3_registration.csv`, summary in `summary.csv`). Median
time from InitialUEMessage to InitialContextSetupRequest: 33.4 ms (null), 29.2 ms (Profile A),
27.5 ms (Profile B), 26.2 ms (scheme 12). The differences are smaller than the run-to-run spread
(p95 between 33.2 and 54.0 ms). Time to PDU session setup was about 250 ms for every scheme
(medians 249.8 to 253.8 ms), dominated by timers and message handling, not by the SUCI. The 10
stock-core runs (third panel) show the patches did not slow down null or Profile A.

### Figure 4: attach storms (E4)

![Figure 4](../results/figures/fig4_storm_latency.png)

Per-UE registration latency grows roughly linearly with the number of simultaneous UEs for every
scheme, because the core processes the registrations one after another. With 100 simultaneous
UEs, the median was 856.5 ms (null), 805.7 ms (Profile A), 806.2 ms (Profile B) and 725.7 ms
(scheme 12) (`summary.csv`, from `e4_storm.csv`). All 1200 UE registrations at N = 100 (3
repetitions x 100 UEs x 4 schemes) completed (`e4_udm_cpu.csv`, `sessions_ok`). Scheme 12 is not
worse than the ECIES profiles; the scheme order at N = 100 is within the variation between
repetitions and should not be read as "post-quantum is faster end to end".

### Figure 5: UDM CPU during storms (E4)

![Figure 5](../results/figures/fig5_udm_cpu.png)

UDM CPU per registered UE at N = 100 (`summary.csv`, from `e4_udm_cpu.csv`): 3.67 ms (null),
5.40 ms (Profile A), 6.07 ms (Profile B), 4.07 ms (scheme 12). This is all UDM work, not only
the SIDF. The ordering matches the in-stack SIDF times of Figure 2. CPU is read in 10 ms ticks, so
the points for 1 and 10 UEs are coarse.

### Figure 6: SIDF capacity model (E5)

![Figure 6](../results/figures/fig6_sidf_capacity.png)

M/M/c queue with the Python mean de-conceal time as service time (`e5_sidf_saturation.csv`).
With one SIDF worker (c = 1) the saturation rate is 10247 registrations per second for Profile A,
6324 for Profile B, 20603 for ML-KEM-768 and 7493 for the hybrid scheme. With four workers the
rates scale by four. On this hardware, de-concealment is not the capacity bottleneck in any
scheme: the measured UDM CPU per registration (Figure 5) is far larger than the SIDF share.

### Figure 7: extra uplink airtime (E5 model)

![Figure 7](../results/figures/fig7_airtime.png)

Scheme 12 adds 1056 bytes compared with Profile A (`e5_airtime.csv`). Under the model in
`e5_airtime_notes.txt` (30 kHz SCS, 0.5 ms slot, 12 data symbols, one layer, no headers or
retransmissions), that is 10 extra slots (5.0 ms) with a 10 PRB QPSK R = 0.30 grant, 2 extra slots
(1.0 ms) with 50 PRB QPSK, and 1 extra slot (0.5 ms) with 50 PRB 16QAM or any 273 PRB grant. The
cost matters most for a UE at the cell edge with a small grant. A first uplink NAS message of
about 1.1 kB may also need RRC segmentation, which the model does not include.

### Figure 8: registration sequence

The sequence diagram (Mermaid) is in [02-suci-explained.md](02-suci-explained.md) and
[09-technical-deep-dive.md](09-technical-deep-dive.md#71-where-the-suci-travels). It marks where
the SUCI is created (UE) and de-concealed (SIDF in the UDM).

### Figure 9: what an eavesdropper sees

![Figure 9](../results/figures/fig9_wireshark_compare.png)

Dissected 5GS mobile identity from real captures (`results/raw/pcap_samples/`). With the null
scheme the MSIN is visible in clear (`MSIN: 0000000001`). With scheme 12 the identity is a 1109
byte scheme output and Wireshark shows the scheme ID as "Unknown (12)".

## Answers to the research questions

**RQ1 (cost).** Size is the real cost: scheme output 45 to 1101 bytes, SUCI string 113 to 2226
characters, NAS Registration Request 65 to 1121 bytes. Compute is not: ML-KEM-768 conceal and
de-conceal took about half the time of Profile A in the same Python harness (41.8 vs 92.0 us and
44.4 vs 88.4 us), and the Open5GS SIDF de-concealed scheme 12 faster than Profile A (90.5 vs
598.5 us median). The hybrid scheme costs roughly X25519 plus ML-KEM (131.7 us conceal in Python).

**RQ2 (integration).** Yes, after patching. A UE registered with scheme 12, the SIDF recovered the
SUPI, and the PDU session and user plane worked (`results/raw/tier3/pq.status`,
`tier3_interop.csv`). Without patches it breaks at well defined places:
UERANSIM supports only schemes 0 and 1 and only 32-byte keys; the Open5GS AMF rejects scheme ID 12
with Registration Reject cause 95 (`src/amf/gmm-handler.c:159-163`, `src/amf/context.c:1911-1916`);
the Open5GS SIDF uses an 8-bit size variable (`lib/sbi/conv.c:28`), fixed key and MSIN lengths,
32-byte key storage and a KDF that aborts on long input (`lib/crypt/ogs-kdf.c:291`). No limit was
hit in NAS, NGAP, the simulated radio or the SBI HTTP/2 path. Full list:
[05-tier3-integration.md](05-tier3-integration.md).

**RQ3 (capacity).** De-concealment does not limit capacity here: the M/M/c model puts saturation
for ML-KEM-768 at about twice the rate of Profile A, and in real storms of 100 UEs the UDM used
less CPU per UE with scheme 12 than with Profile A or B. The larger message costs up to 10 extra
uplink slots (5 ms) for a UE with a small, robust grant, and about one slot otherwise.

## Other observations

- **AUSF context pool.** In long storm series the Open5GS AUSF ran out of UE contexts, because it
  keeps one context per SUCI string and every protected registration has a new SUCI. This applies
  to all protected schemes. Details: [05-tier3-integration.md](05-tier3-integration.md) and
  `results/raw/e4/invalid_ausf_pool/README.md`.
- **Timing noise.** Laptop timings varied between runs before the machine was idle (for example a
  Profile A de-conceal median of 103 us in one earlier run and 155 us in another). The reported
  Python values are medians over three runs on an idle machine.
