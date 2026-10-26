# 11. The testbed in action: Open5GS, UERANSIM and Wireshark/tshark

This document shows, with data from the actual runs, how the three tools in this project were
used and what they produced. Every figure is generated from captures and logs by
`experiments/stack_data.py` (extraction to CSV) and `experiments/stack_figures.py` (plots).
Numbers are taken from the CSV files named next to them.

| Tool | Version | Role |
|---|---|---|
| Open5GS | v2.8.0 | 5G standalone core: NRF, SCP, AMF, SMF, UPF, AUSF, UDM (with SIDF), UDR, PCF, NSSF, BSF |
| UERANSIM | v3.3.0 | simulated gNB (`nr-gnb`) and UEs (`nr-ue`), radio link simulated over UDP |
| tshark (Wireshark) | 4.6.4 | packet capture on the loopback interface and protocol dissection (NGAP, NAS-5GS, HTTP/2, JSON) |

Versions: [versions.md](versions.md).

## 1. Testbed topology

![Figure 10](../results/figures/fig10_testbed.png)

All network functions run on one Linux host with loopback addresses from `config/open5gs/`.
UERANSIM's gNB connects to the AMF over NGAP/SCTP (N2, port 38412) and to the UPF over GTP-U
(N3). Control-plane network functions talk HTTP/2 on port 7777 through the SCP. The SUCI is
computed in `nr-ue` and travels UE, gNB, AMF, AUSF, UDM, where the SIDF recovers the SUPI.

## 2. One registration, message by message

![Figure 11](../results/figures/fig11_message_sequence.png)

A real scheme 12 registration from `results/raw/tier3/pq.pcap`, reconstructed from NGAP and
HTTP/2 messages (`results/processed/stack_sequence.csv`, 44 messages, 3 of which carry the SUCI).
The SUCI-carrying messages are the NGAP InitialUEMessage (with the NAS Registration Request), the
AMF to AUSF `ue-authentications` request (SUCI in the JSON body), and the AUSF to UDM
`generate-auth-data` request (SUCI in the URI). After authentication, every request uses the
SUPI (`imsi-...`), so the large SUCI appears only in those three messages.

![Figure 16](../results/figures/fig16_wireshark_packet_list.png)

The same registration as tshark's packet list (`results/processed/wireshark_packet_list.csv`).
The InitialUEMessage frame carrying the scheme 12 SUCI is 1238 bytes long on the wire.

## 3. One registration seen by the UERANSIM UE

![Figure 13](../results/figures/fig13_ue_gnb_timeline.png)

Phases of the registration from the UERANSIM UE log (`results/processed/stack_ue_events.csv`,
time since the UE started; the gNB events are in the same file). For scheme 12, the UE computed the SUCI 3.0 ms after start, entered RRC-CONNECTED
and sent the Registration Request; the Registration Accept arrived at 262.0 ms, the PDU session
at 484.0 ms, and the `uesimtun0` tunnel was up at 567.0 ms. Most of that time is spent in timers
and in the core's subscriber data handling, not in the SUCI (compare Figure 3 in
[07](07-results-and-discussion.md)).

## 4. Where the bytes go

![Figure 12](../results/figures/fig12_interface_bytes.png)

Payload bytes per interface for one registration per scheme
(`results/processed/stack_interface_bytes.csv`; NRF traffic excluded because its heartbeats vary
between runs). The figure compares Profile A and scheme 12 on the six busiest interfaces. Only three grow: N2 (1206 to 3323
bytes), the SBI towards the AUSF (1007 to 3120) and the SBI towards the UDM (5879 to 7420). The
interfaces towards the UDR, PCF, SMF, BSF and AMF differ by at most 23 bytes between the two schemes.

![Figure 17](../results/figures/fig17_protocol_hierarchy.png)

tshark's protocol hierarchy statistics (`tshark -z io,phs`,
`results/processed/wireshark_protocol_hierarchy.csv`) agree: NGAP bytes per registration were
2082 (null), 2162 (Profile A), 2170 (Profile B) and 4266 (scheme 12).

## 5. Attach storms as seen by the core

![Figure 14](../results/figures/fig14_storm_progress.png)

`nr-ue -n 100` starts 100 UEs at once. The AMF reached InitialContextSetupRequest for all 100
UEs in every scheme; the last one after 2287.2 ms (Profile A), 2763.8 ms (Profile B),
2854.7 ms (scheme 12) and 2978.4 ms (null) (`results/processed/stack_storm_progress.csv`,
repetition 1). The figure shows Profile A and scheme 12; the other schemes are in the CSV. The order
between schemes changes between repetitions (compare Figure 4 in
[07](07-results-and-discussion.md)), so it should not be read as a ranking.

![Figure 18](../results/figures/fig18_io_graph.png)

Wireshark-style I/O graph of the same storms (`results/processed/wireshark_io_graph.csv`):
NGAP packets per 100 ms on N2, Profile A against scheme 12. The time axis starts when the
capture starts, one to two seconds before the UEs (the offset differs per run). Both schemes show the same burst pattern of a
core working through 100 registrations.

## 6. Logs from both projects

![Figure 15](../results/figures/fig15_log_evidence.png)

Characteristic log lines (`results/raw/stack/log_excerpts.txt`): the version banners, the gNB's
NG Setup, the UE computing a scheme 12 SUCI, the AMF receiving the InitialUEMessage, the UDM
loading the ML-KEM-768 key and the SIDF recovering the SUPI. The `[SUCI]` and `[SIDF]` lines are
added by this project's patches ([05](05-tier3-integration.md)).

## 7. How the captures were made and analysed

- **Capture:** `experiments/run_registration.sh` starts
  `tshark -i lo -f "sctp port 38412 or tcp port 7777" -w -` before the gNB and UE, so every
  NGAP (N2) and SBI (HTTP/2) message of the run is recorded.
- **Dissection:** SBI traffic is cleartext HTTP/2 (h2c) on port 7777, which tshark does not
  detect by default; all analysis uses `-d tcp.port==7777,http2`.
- **Analysis:** fields are extracted with `tshark -T fields` (for example `ngap.procedureCode`,
  `ngap.RAN_UE_NGAP_ID`, `nas-5gs.mm.suci.scheme_id`, `http2.headers.path`) into CSV, never with
  hand-copied values. Statistics use `tshark -z io,phs`.
- **Viewing in Wireshark:** open a file from `results/raw/pcap_samples/`, use
  *Analyze > Decode As* to set TCP port 7777 to HTTP2, then try the display filters
  `ngap.procedureCode == 15` (Registration Request with the SUCI), `nas-5gs.mm.suci.scheme_id`,
  and `http2.headers.path contains "suci"`.
- **Reproduce the figures:** `.venv/bin/python experiments/stack_data.py` (needs the raw captures
  and logs from a local run) and `make figures`.
