# Results and handoff

## 1. Summary

This repository runs a complete 5G standalone core (Open5GS v2.8.0) with a simulated gNB and UEs
(UERANSIM v3.3.0) on one Linux machine, and adds a post-quantum SUCI protection scheme
(scheme 12: ML-KEM-768 KEM with the TS 33.501 Annex C symmetric layer) next to ECIES Profiles A
and B. A UE registered on the real core with scheme 12: the SIDF in the UDM recovered the SUPI and
the PDU session and user plane worked. The post-quantum SUCI is about 24 times larger (1101 vs 45
bytes of scheme output), but it was not slower to compute, did not increase registration latency,
and did not increase UDM CPU under attach storms of up to 100 UEs on this hardware. Getting there
required patches in the UE (UERANSIM), the serving AMF and the UDM, at places where the code
hardcoded the scheme list or elliptic-curve sizes. Schemes 12 and 13 are a research prototype in
the proprietary scheme ID range, not a standard.

## 2. Results table

From `results/processed/summary.csv` (column sources in `results/processed/summary_notes.txt`).
Python timings are the median of three run medians; "UDM" is the in-stack Open5GS SIDF.

| Scheme | Scheme output (B) | SUCI string (chars) | NAS Reg. Request (B) | Conceal, Python (us) | De-conceal, Python (us) | De-conceal, UDM (us) | Registration, 1 UE (ms) | Registration, 100 UEs (ms) | Worked on core |
|---|---|---|---|---|---|---|---|---|---|
| null (0) | 5 | 33 | 25 | 0.104 | 0.111 | 2.8 | 33.4 | 856.5 | yes |
| Profile A (1) | 45 | 113 | 65 | 92.0 | 88.4 | 598.5 | 29.2 | 805.7 | yes |
| Profile B (2) | 46 | 115 | 66 | 142.7 | 149.1 | 1557.0 | 27.5 | 806.2 | yes (patched UE) |
| ML-KEM-768 (12) | 1101 | 2226 | 1121 | 41.8 | 44.4 | 90.5 | 26.2 | 725.7 | yes (patched UE, AMF, UDM) |
| Hybrid (13) | 1133 | 2290 | not measured | 131.7 | 129.0 | not implemented in C | not measured | not measured | not tested |
| ML-KEM-512 (bench) | 781 | 1586 | not measured | 37.0 | 40.2 | not implemented in C | not measured | not measured | not tested |
| ML-KEM-1024 (bench) | 1581 | 3186 | not measured | 45.9 | 50.7 | not implemented in C | not measured | not measured | not tested |

## 3. Figures

Full interpretations: [docs/07-results-and-discussion.md](docs/07-results-and-discussion.md).

- [Fig. 1, sizes](results/figures/fig1_sizes.png): the post-quantum schemes are one to two orders of
  magnitude larger than ECIES in both the binary scheme output and the SUCI text string.
- [Fig. 2, compute](results/figures/fig2_compute.png): ML-KEM is faster than ECIES in Python and in
  the Open5GS UDM; UE-side times inside UERANSIM have long tails and reflect simulator code.
- [Fig. 3, single-UE latency](results/figures/fig3_registration_latency.png): all schemes register
  in about 26 to 33 ms (median); differences are within run-to-run spread; the patches add no
  visible overhead to null or Profile A.
- [Fig. 4, storm latency](results/figures/fig4_storm_latency.png): latency grows roughly linearly
  with simultaneous UEs for every scheme; scheme 12 is not worse.
- [Fig. 5, UDM CPU](results/figures/fig5_udm_cpu.png): per-UE UDM CPU at 100 UEs follows the SIDF
  cost: Profile B highest, then Profile A, then scheme 12, then null.
- [Fig. 6, SIDF capacity model](results/figures/fig6_sidf_capacity.png): saturation for ML-KEM-768
  is about twice that of Profile A with the same number of workers.
- [Fig. 7, airtime model](results/figures/fig7_airtime.png): the extra 1056 bytes cost 10 slots
  (5 ms) with a 10 PRB QPSK grant, one slot with larger grants.
- [Fig. 8, sequence diagram](results/figures/fig8_registration_sequence.png): where the SUCI is
  created (UE) and de-concealed (SIDF in the UDM). Source: Mermaid in
  [docs/09](docs/09-technical-deep-dive.md#71-where-the-suci-travels). Other diagrams:
  [fig8b, changes per network function](results/figures/fig8b_pq_changes.png),
  [fig8c, core architecture](results/figures/fig8c_core_architecture.png),
  [fig8d, full registration flow](results/figures/fig8d_registration_overview.png).
- [Fig. 9, wire view](results/figures/fig9_wireshark_compare.png): the null scheme shows the MSIN in
  clear; scheme 12 shows only the 1109-byte concealed identity.

## 4. Tier 3 outcome

Success. Scheme 12 registered end to end on the patched core (`results/raw/tier3/pq.status`:
`success=1 ping=ok`; UDM log `[SIDF] scheme=12 suci_len=2226 supi=imsi-999700000000001`;
`results/processed/tier3_interop.csv`: the captured SUCI also de-conceals correctly with the
independent Python code). Stock Open5GS rejects scheme 12 in the serving AMF (cause 95), and stock
UERANSIM supports neither Profile B nor scheme 12. Scheme 13 (hybrid) exists only in Python. All
changes and limits: [docs/05-tier3-integration.md](docs/05-tier3-integration.md).

## 5. Human checklist

1. Open `results/raw/pcap_samples/tier1_null.pcap` and `tier3_scheme12.pcap` in Wireshark. Filter
   `ngap.procedureCode == 15`, expand the NAS Registration Request, and confirm: MSIN visible for
   the null scheme; protection scheme ID 12 and a 1109-byte mobile identity for scheme 12.
2. In the same captures, filter `http2.headers.path contains "suci"` (Decode As: TCP port 7777 as
   HTTP/2) and check the SUCI string in the UDM request URI.
3. Rerun `make bench` on your machine and compare with `results/processed/e1_repeatability.csv`.
   Absolute values will differ; the ordering (ML-KEM faster than ECIES) is what to check.
4. Sanity check the surprising result that ML-KEM is faster than ECIES: compare the native liboqs
   numbers (`results/processed/e1_native_liboqs.csv`) with liboqs' own published benchmarks for
   your CPU class, and note that liboqs uses AVX2 code.
5. Check that the UDM-side SIDF numbers (`results/processed/e6_native_timings.csv`) are plausible
   by grepping `[SIDF]` in `results/raw/e3/pq/udm.log`.
6. Read `results/raw/e4/invalid_ausf_pool/README.md` and decide how to present the AUSF context
   pool finding.
7. Confirm that the airtime model assumptions in `results/processed/e5_airtime_notes.txt` match
   what your course expects, or replace them with lab measurements (docs/08).

## 6. How to reproduce

```bash
make setup build keys   # dependencies, builds, local test keys (needs sudo)
make test               # unit tests
make experiments        # E1 to E6 (starts and stops the core; about 45 minutes)
make figures            # figures from results/processed/
```

Details: [docs/04-setup.md](docs/04-setup.md) and [docs/06-experiments.md](docs/06-experiments.md).

## 7. Suggested report outline

| Chapter | Content | Docs and figures |
|---|---|---|
| 1. Introduction | identity privacy, IMSI catchers, quantum threat, research questions | docs/09 sections 1 and 3 |
| 2. Background | 5G SA architecture, SUCI, ECIES, ML-KEM | docs/01, docs/02, docs/09 sections 2 and 4, Fig. 8 |
| 3. Design | KEM-DEM scheme 12, hybrid scheme 13, scheme ID range | docs/03, docs/09 section 5 |
| 4. Implementation | testbed, patches, limits found | docs/04, docs/05, docs/09 section 7 |
| 5. Method | experiments and markers | docs/06 |
| 6. Results | RQ1 to RQ3 | docs/07, Fig. 1 to 7 and 9 |
| 7. Discussion and limitations | what a laptop cannot show, lab plan | docs/08 |
| 8. Related work | prior work | docs/09 section 6 |
| 9. Real-world deployment | blockers, migration paths, standardization | docs/10 |
