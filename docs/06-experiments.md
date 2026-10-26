# Experiments: method

This page describes how each experiment is run and what it measures. It gives no results. Results are in `results/processed/` and are discussed in [09-technical-deep-dive.md](09-technical-deep-dive.md). Limits of the setup are in [08-limitations-and-lab.md](08-limitations-and-lab.md).

Schemes 12 (ML-KEM-768) and 13 (hybrid X25519 + ML-KEM-768) are a research prototype. They are not standardized. Scheme 13 exists only in the Python package. Protection scheme IDs: 0 null, 1 Profile A, 2 Profile B, 12 ML-KEM-768, 13 hybrid.

Terms used below: SUCI (Subscription Concealed Identifier), SUPI (Subscription Permanent Identifier), SIDF (Subscription Identifier De-concealing Function, part of the UDM, Unified Data Management), NGAP (NG Application Protocol, between gNB and AMF), NAS (Non-Access Stratum), AMF (Access and Mobility Management Function), AUSF (Authentication Server Function), KEM (key encapsulation mechanism), UE (user equipment), gNB (5G base station), PCAP (packet capture).

## Environment

- CPU, kernel, Python and library versions of the E1 run: `results/raw/e1/env.txt`. It also records the machine load just before the run.
- Versions of liboqs, Open5GS, UERANSIM and the toolchain: [versions.md](versions.md).
- Everything runs on one machine under WSL2: the core, the gNB, the UEs and the capture.

## E1: cryptographic microbenchmarks

**Purpose.** Compare the compute cost of key generation, concealing and de-concealing for all schemes.

**What is measured.** Time per call of `keygen`, `conceal` and `deconceal` for null, profile-a, profile-b, mlkem512, mlkem768, mlkem1024 and hybrid, using the `pqsuci` Python package. Also the C speed of the three ML-KEM sizes in liboqs.

**Python benchmark.**

- Command: `bash bench/e1_repeat.sh 3` (calls `bench/e1_micro.py` three times). A single run is `.venv/bin/python bench/e1_micro.py --iterations 2000`.
- Per scheme and operation: 200 warm-up calls, then 2000 timed calls.
- Clock: `time.perf_counter_ns()` around each call. The garbage collector is disabled during timing.
- For `deconceal`, the 2000 inputs are generated before timing, so the timed loop does not include `conceal`.
- The plaintext is the MSIN `0000000001`.
- The whole benchmark is repeated 3 times on an idle machine, because laptop timings vary between runs (CPU frequency scaling, WSL scheduling).
- Outputs:
  - `results/raw/e1/python_timings.csv`: every timed call (last run).
  - `results/raw/e1/repeat_1/` to `repeat_3/`: summary CSV and `env.txt` of each run.
  - `results/processed/e1_micro_python.csv`: median, 95th percentile, mean and standard deviation (last run).
  - `results/processed/e1_repeatability.csv`: for each scheme and operation, the median of the 3 run medians, and the smallest and largest run median.

**Native benchmark.**

- Command: `bash bench/e1_native.sh`.
- Runs liboqs `speed_kem` for ML-KEM-512, ML-KEM-768 and ML-KEM-1024, 3 seconds per algorithm. `bench/parse_speed_kem.py` turns the text into a CSV.
- Outputs: `results/raw/e1/speed_kem.txt`, `results/processed/e1_native_liboqs.csv` (keygen, encaps, decaps; mean time and mean cycles).
- This measures the KEM only, not the full SUCI construction (no KDF, MAC or AES).

## E2: sizes

**Purpose.** Show how much larger the SUCI gets for each scheme.

**What is measured.**

- Computed sizes: home network public key, scheme output, SUCI string, and NAS 5GS mobile identity. The method for each column is in `results/processed/e2_sizes_notes.txt`.
- Sizes seen on the wire: the scheme output length and the SUCI string length in captures (from the interop check below), and the size of the NAS Registration Request in the first NGAP message of each registration run (from the E3 and E4 runs).

**Command.** `.venv/bin/python experiments/e2_sizes.py`

**Inputs.** `pqsuci.schemes` for the computed part. PCAP files for the wire part.

**Outputs.**

- `results/processed/e2_sizes_computed.csv`, `results/processed/e2_sizes_notes.txt`.
- Wire sizes: `results/processed/tier1_interop.csv`, `results/processed/tier3_interop.csv`, and the column `nas_reg_request_bytes` in `results/processed/e3_registration.csv` and `results/processed/e4_storm.csv`.

## E3: single-UE registration latency

**Purpose.** Measure how long one registration takes for each scheme, and check that the patches do not slow down the existing schemes.

**What is measured.** Time from the first NGAP message of a registration to the point where the registration is accepted, and to the start of the PDU session setup. Times come from a capture of the NGAP traffic on the loopback interface.

**Markers.** NGAP headers are not ciphered, so the markers are visible even though NAS is protected.

| Marker | NGAP message | procedureCode | Type |
|---|---|---|---|
| start | InitialUEMessage | 15 | initiatingMessage |
| registered | InitialContextSetupRequest | 14 | initiatingMessage |
| session | PDUSessionResourceSetupRequest | 29 | initiatingMessage |

In Open5GS the InitialContextSetupRequest carries the NAS Registration Accept, so it marks the end of registration. The message order was checked in the dissected capture of the first interop test (InitialUEMessage with Registration request, Authentication request and response, Security mode command, InitialContextSetupRequest and Response, PDUSessionResourceSetupRequest).

**Parsing details** (`experiments/parse_ngap.py`).

- tshark reads the fields `frame.time_epoch`, `ngap.NGAP_PDU`, `ngap.procedureCode`, `ngap.RAN_UE_NGAP_ID` and `ngap.NAS_PDU`.
- `ngap.NGAP_PDU` equal to 0 means initiatingMessage. This separates requests from responses that share a procedure code.
- Several NGAP PDUs can share one SCTP frame. tshark then joins their values with `|` (aggregator), and the parser splits them again.
- UEs are matched across messages by RAN-UE-NGAP-ID. The first occurrence of each marker is used.
- Each run starts tshark, a fresh gNB and the UE (`experiments/run_registration.sh`). Registration latency therefore excludes NG Setup.
- `registration_ms` is registered minus start. `session_ms` is session minus start. `nas_reg_request_bytes` is the NAS-PDU length in the InitialUEMessage.

**Commands.** Part of `scripts/run_all.sh`. The calls are:

```bash
# patched core: 30 runs per scheme
CORE=pq experiments/e3_registration.sh 30 null profileA profileB pq
# stock core, patch-overhead check: 10 runs
CORE=stock experiments/e3_registration.sh 10 null profileA
```

The run counts are set by `E3_RUNS` (default 30) and `E3_CHECK_RUNS` (default 10).

**Inputs.** UE configurations `config/ueransim/ue-null.yaml`, `ue-profileA.yaml`, `ue-profileB.yaml`, `ue-pq.yaml`; test keys in `config/keys/`; 120 test subscribers.

**Outputs.**

- `results/raw/e3/<core>/<scheme>/run_NN.pcap`, `.ue.log`, `.gnb.log`, `.status`.
- `results/processed/e3_registration.csv` (column `core` is `stock` or `pq`).

## E4: attach storms

**Purpose.** See how latency and UDM CPU use change when many UEs register at once.

**What is measured.**

- Per-UE registration and session latency, from the same NGAP markers as E3.
- CPU time used by the UDM process: the change in `utime + stime` in `/proc/<pid>/stat` between the start and the end of the run, divided by the clock tick rate. The tick is 10 ms, so values for small N are coarse.
- A `pidstat` time series of the UDM process, one sample per second.

**Design.** N in {1, 10, 50, 100} UEs started with one `nr-ue -n N`, 3 repetitions each, for null, Profile A, Profile B and scheme 12. The core is stopped and started again before each scheme. The AUSF keeps one context per SUCI string, and the test UEs are stopped without deregistering. A long series of protected registrations would otherwise fill the AUSF context pool. Runs that hit this limit are kept as evidence in `results/raw/e4/invalid_ausf_pool/` (see its README) and excluded from the results. See also [05-tier3-integration.md](05-tier3-integration.md).

**Command.**

```bash
CORE=pq experiments/e4_storm.sh 3 "1 10 50 100" null profileA profileB pq
```

Run counts and sizes are set by `E4_REPS` and `E4_NS` in `scripts/run_all.sh`.

**Outputs.**

- `results/raw/e4/pq/<scheme>/n<N>/rep_<k>.pcap`, `.pidstat`, `.ue.log`, `.gnb.log`, `.status`.
- `results/processed/e4_storm.csv` (one row per UE).
- `results/processed/e4_udm_cpu.csv` (one row per run: CPU seconds, wall seconds, average CPU percent, sessions established).

## E5: models

**Purpose.** Estimate effects that the single-machine setup cannot show: SIDF capacity and radio cost.

**Command.** `.venv/bin/python experiments/e5_models.py`

**Inputs.** `results/processed/e1_micro_python.csv` and `results/processed/e2_sizes_computed.csv`.

**Outputs.** `results/processed/e5_sidf_capacity.csv`, `e5_sidf_saturation.csv`, `e5_airtime.csv`, `e5_airtime_notes.txt`.

### SIDF capacity (M/M/c queue)

- The SIDF is modelled as an M/M/c queue (Erlang C), with c = 1, 2 and 4 servers.
- The mean service time is the mean Python `deconceal` time per scheme from `e1_micro_python.csv`.
- Mean response time is queueing delay plus service time.
- The model includes only de-concealment. It ignores UDM, UDR (Unified Data Repository), SBI (service-based interface) and AUSF work, network latency and batching.
- The null scheme is excluded because it has no cryptography.
- The model gives the saturation rate (c divided by the service time) and the arrival rate at which the mean response time reaches 10 ms.

### Uplink airtime

These are the assumptions, as stated in `experiments/e5_models.py` and `results/processed/e5_airtime_notes.txt`:

- NR (New Radio), 30 kHz subcarrier spacing (0.5 ms slot), 1 layer.
- 14 OFDM symbols per slot, of which 12 carry data (2 assumed for DMRS and control), 12 subcarriers per PRB (physical resource block).
- `bits_per_slot = PRB * 12 * 12 * Qm * R`.
- No transport block size quantization, no MAC/RLC/PDCP headers, no HARQ retransmissions.
- PRB grants 10, 50 and 273. QPSK with R = 0.30, 16QAM with R = 0.50, and 64QAM with R = 0.75. These are illustrative mid-range choices, not rows of a specific MCS table.
- `extra_bytes` is the scheme output size minus that of Profile A (or null).
- `extra_slots = ceil(extra_bits / bits_per_slot)`, or 0 if the difference is not positive. `extra_time_ms = extra_slots * 0.5`.

A large first uplink NAS message may also need RRC (Radio Resource Control) segmentation. The model does not include this.

## E6: native timings

**Purpose.** Time the C and C++ implementations inside the patched UERANSIM and Open5GS.

**What is measured.** The patched code logs one line per operation.

- UE: `[SUCI] scheme= output_bytes= conceal_us=` (ephemeral key or encapsulation, KDF, AES and MAC).
- UDM: `[SIDF] scheme= suci_len= supi= deconceal_us=` (the whole `ogs_supi_from_suci()` call: string parsing, hex decoding, decapsulation, KDF, MAC, AES). Failed de-concealments are skipped.

**Command.** Run at the end of `scripts/run_all.sh`:

```bash
.venv/bin/python experiments/parse_native_logs.py \
  --ue-logs 'results/raw/e3/pq/*/*.ue.log' --udm-log results/raw/e3/pq/udm.log
```

**Inputs.** The UE logs and the copy of the UDM log taken after the E3 runs on the patched core.

**Outputs.** `results/processed/e6_native_timings_raw.csv` (one row per log line) and `results/processed/e6_native_timings.csv` (count, median, 95th percentile and mean per side and scheme).

E6 also includes the E3 and E4 runs with scheme 12 (the `pq` UE configuration), described above.

## Interoperability check

**Purpose.** Show that the SUCI crosses a real core and can be de-concealed outside it.

**What is measured.** For each capture, the SUCI is read twice: from the NAS Registration Request in the NGAP InitialUEMessage, and from the SBI request path the AUSF sends to the UDM (`/nudm-ueau/v1/<suci>/...`). The SUCI is de-concealed with the Python SIDF and the test private key, and the result is compared with the IMSI configured in the UE (`999700000000001`). The script also checks that the NAS and SBI scheme outputs are identical, and saves the dissected 5GS mobile identity text.

**Commands.**

```bash
.venv/bin/python experiments/tier1_interop.py results/raw/tier1/*.pcap
.venv/bin/python experiments/tier1_interop.py results/raw/tier3/*.pcap \
  --out results/processed/tier3_interop.csv
```

**Inputs.** Captures from a single registration with ping through the UE tunnel (`experiments/run_registration.sh ... -p`). Tier 1 is the stock core with null and Profile A. Tier 3 is the patched core with null, Profile A, Profile B and scheme 12.

**Outputs.** `results/processed/tier1_interop.csv`, `results/processed/tier3_interop.csv`, and `results/raw/tier*/<name>.mobile_identity.txt`. Sample captures are in `results/raw/pcap_samples/`.

## Reproduce

```bash
make setup build keys     # packages, builds (liboqs, Open5GS, UERANSIM, patched copies), test keys
make experiments          # runs scripts/run_all.sh
make figures
```

`scripts/run_all.sh` starts and stops the core itself and adds the test subscribers (the `make core-up subscribers` steps), so these do not need to be run by hand. It needs `sudo` for the packet capture and the UE tunnel. Keep the machine idle during E1. The E1 to E5 outputs are rewritten on every run; the E3 and E4 raw runs that already succeeded are skipped.
