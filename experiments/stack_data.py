"""Extract evidence of the simulated 5G stack (Open5GS + UERANSIM) from captures and logs.

Inputs (written by experiments/run_registration.sh and the E4 runs):
  results/raw/tier3/<scheme>.pcap|.ue.log|.gnb.log   one registration per scheme, patched core
  results/raw/e4/pq/<scheme>/n100/rep_1.pcap           100-UE attach storm per scheme
  runtime/log/<nf>.log (optional)                      Open5GS logs, for the log excerpt
Outputs:
  results/processed/stack_sequence.csv         messages of one scheme 12 registration
  results/processed/stack_interface_bytes.csv  bytes per interface and scheme
  results/processed/stack_ue_events.csv        UERANSIM UE and gNB events with times
  results/processed/stack_storm_progress.csv   registered UEs over time in 100-UE storms
  results/raw/stack/log_excerpts.txt           selected log lines from both projects
  results/processed/wireshark_packet_list.csv  packet list of the scheme 12 registration (tshark)
  results/processed/wireshark_protocol_hierarchy.csv  tshark -z io,phs per scheme
  results/processed/wireshark_io_graph.csv     NGAP and HTTP/2 packets per 100 ms in storms

SBI clients in Open5GS send from 127.0.0.1 and go through the SCP (127.0.0.200), so the
consumer of a request is inferred from its service API (for example nausf-auth is called by the
AMF). Only the SCP-to-producer leg is counted, so no request is counted twice.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from parse_ngap import ue_times  # noqa: E402

RAW = ROOT / "results" / "raw"
PROC = ROOT / "results" / "processed"
SCP_IP = "127.0.0.200"
GNB_IP = "127.0.0.1"
AMF_NGAP_IP = "127.0.0.5"
SCHEMES = {"null": "null", "profileA": "profileA", "profileB": "profileB", "pq": "pq"}
NGAP_NAMES = {
    "21": "NGSetup",
    "15": "InitialUEMessage",
    "4": "DownlinkNASTransport",
    "46": "UplinkNASTransport",
    "14": "InitialContextSetup",
    "29": "PDUSessionResourceSetup",
}


def nf_addresses() -> dict[str, str]:
    """Map SBI server IP -> NF name, read from config/open5gs/<nf>.yaml."""
    out = {}
    for path in sorted((ROOT / "config" / "open5gs").glob("*.yaml")):
        if path.stem.endswith("-pq"):
            continue
        text = path.read_text()
        match = re.search(r"sbi:\s*\n\s*server:\s*\n\s*- address: (\S+)", text)
        if match:
            out[match.group(1)] = path.stem.upper()
    return out


def consumer_of(path: str) -> str:
    """Infer which NF sent an SBI request from its service API path."""
    rules = [
        ("/nausf-auth/", "AMF"),
        ("/nudm-ueau/", "AUSF"),
        ("/nudr-dr/", "PCF" if "policy-data" in path else "UDM"),
        ("/nudm-sdm/", "SMF" if "/sm-data" in path else "AMF"),
        ("/nudm-uecm/", "SMF" if "smf-registrations" in path else "AMF"),
        ("/npcf-am-policy-control/", "AMF"),
        ("/npcf-ue-policy-control/", "AMF"),
        ("/npcf-smpolicycontrol/", "SMF"),
        ("/nsmf-pdusession/", "AMF"),
        ("/namf-comm/", "SMF"),
        ("/nnssf-", "AMF"),
        ("/nbsf-", "PCF"),
        ("/nnrf-", "NF"),
    ]
    return next((nf for key, nf in rules if key in path), "?")


def tshark(pcap: Path, display_filter: str, fields: list[str]) -> list[list[str]]:
    """Return tshark field rows (aggregated values joined with '|')."""
    cmd = ["tshark", "-r", str(pcap), "-d", "tcp.port==7777,http2", "-Y", display_filter]
    cmd += ["-T", "fields", "-E", "separator=\t", "-E", "aggregator=|"]
    for f in fields:
        cmd += ["-e", f]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line.strip()]


def sequence(pcap: Path, nfs: dict[str, str]) -> list[dict[str, object]]:
    """NGAP initiating messages and SBI requests (producer leg) of one registration."""
    rows: list[dict[str, object]] = []
    for t, pdu, proc, src in tshark(
        pcap,
        "ngap",
        ["frame.time_relative", "ngap.NGAP_PDU", "ngap.procedureCode", "ip.src"],
    ):
        for p, c in zip(pdu.split("|"), proc.split("|"), strict=False):
            if p != "0":
                continue
            name = NGAP_NAMES.get(c, f"NGAP proc {c}")
            gnb_to_amf = src == GNB_IP
            rows.append(
                {
                    "t_s": float(t),
                    "interface": "N2 (NGAP/SCTP)",
                    "src": "gNB" if gnb_to_amf else "AMF",
                    "dst": "AMF" if gnb_to_amf else "gNB",
                    "label": name,
                    "carries_suci": c == "15",
                }
            )
    for t, dst, paths in tshark(
        pcap,
        f"http2.headers.path && ip.dst != {SCP_IP} && tcp.dstport == 7777",
        ["frame.time_relative", "ip.dst", "http2.headers.path"],
    ):
        producer = nfs.get(dst, dst)
        for path in paths.split("|"):
            consumer = consumer_of(path)
            if consumer == "NF":  # NRF discovery and heartbeat, not part of the procedure
                continue
            service = path.split("/")[1]
            rows.append(
                {
                    "t_s": float(t),
                    "interface": f"SBI (HTTP/2) to {producer}",
                    "src": consumer,
                    "dst": producer,
                    "label": f"{service} {path.split('/')[-1][:28]}",
                    # the SUCI is in the URI towards the UDM and in the body of the first AUSF call
                    "carries_suci": "suci-0-" in path or path.endswith("/ue-authentications"),
                }
            )
    rows.sort(key=lambda r: r["t_s"])
    t0 = next(r["t_s"] for r in rows if r["label"] == "InitialUEMessage")
    for r in rows:
        r["t_ms"] = round((r.pop("t_s") - t0) * 1000, 3)
    return [r for r in rows if r["t_ms"] >= 0]


def interface_bytes(pcap: Path, scheme: str, nfs: dict[str, str]) -> list[dict[str, object]]:
    """Payload bytes per interface: SCTP data on N2, TCP payload on each SBI producer leg."""
    totals: dict[str, list[int]] = {}
    for types, lengths in tshark(pcap, "ngap", ["sctp.chunk_type", "sctp.chunk_length"]):
        # DATA chunks (type 0) only; chunk length includes a 16-byte DATA chunk header
        pairs = zip(types.split("|"), lengths.split("|"), strict=False)
        b = sum(int(n) - 16 for t, n in pairs if t == "0" and n)
        entry = totals.setdefault("N2 gNB-AMF", [0, 0])
        entry[0] += b
        entry[1] += 1
    for src, dst, _sport, dport, tlen in tshark(
        pcap,
        f"tcp.len > 0 && (tcp.port == 7777) && ip.addr != {SCP_IP}",
        ["ip.src", "ip.dst", "tcp.srcport", "tcp.dstport", "tcp.len"],
    ):
        producer_ip = dst if dport == "7777" else src
        if producer_ip == GNB_IP:
            continue
        name = nfs.get(producer_ip, producer_ip)
        entry = totals.setdefault(f"SBI {name}", [0, 0])
        entry[0] += int(tlen)
        entry[1] += 1
    return [
        {"scheme": scheme, "interface": k, "payload_bytes": v[0], "packets": v[1]}
        for k, v in sorted(totals.items())
    ]


EVENT_PATTERNS = [
    ("UE", r"switches to state \[(MM-[A-Z/-]+|RRC-[A-Z]+|CM-[A-Z]+)\]", None),
    ("UE", r"\[SUCI\] scheme=(\d+)", "SUCI computed (scheme {0})"),
    ("UE", r"(Sending Initial Registration)", "{0}"),
    ("UE", r"(Registration accept received)", "{0}"),
    ("UE", r"(PDU Session establishment is successful)", "{0}"),
    ("UE", r"TUN interface\[(uesimtun\d+)", "TUN {0} up"),
    ("gNB", r"(NG Setup procedure is successful)", "{0}"),
    ("gNB", r"(RRC Setup for UE\[1\])", "{0}"),
    ("gNB", r"(Initial NAS message received from UE\[1\])", "{0}"),
    ("gNB", r"(Initial Context Setup Request received)", "{0}"),
    ("gNB", r"(PDU session resource\(s\) setup)", "{0}"),
]
TS_RE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\]")


def _seconds(ts: str) -> float:
    h, m, s = ts.split(" ")[1].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def ue_events(scheme: str) -> list[dict[str, object]]:
    """UERANSIM UE and gNB events for one registration, relative to the first UE line."""
    events = []
    for comp, suffix in (("UE", "ue"), ("gNB", "gnb")):
        path = RAW / "tier3" / f"{scheme}.{suffix}.log"
        if not path.exists():
            continue
        for line in path.read_text(errors="replace").splitlines():
            ts = TS_RE.match(line)
            if not ts:
                continue
            for c, pattern, fmt in EVENT_PATTERNS:
                m = re.search(pattern, line)
                if c == comp and m:
                    text = m.group(1) if fmt is None else fmt.format(*m.groups())
                    events.append(
                        {"scheme": scheme, "component": comp, "t": _seconds(ts[1]), "event": text}
                    )
    ue_start = min((e["t"] for e in events if e["component"] == "UE"), default=0.0)
    for e in events:
        e["t_ms"] = round((e.pop("t") - ue_start) * 1000, 1)
    return sorted(events, key=lambda e: e["t_ms"])


def storm_progress(pcap: Path, scheme: str) -> list[dict[str, object]]:
    """Cumulative number of UEs that reached InitialContextSetupRequest over time."""
    times = ue_times(pcap)
    starts = [u.start for u in times.values() if u.start is not None]
    done = sorted(u.registered for u in times.values() if u.registered is not None)
    if not starts:
        return []
    t0 = min(starts)
    return [
        {"scheme": scheme, "t_ms": round((t - t0) * 1000, 3), "registered_ues": i + 1}
        for i, t in enumerate(done)
    ]


def log_excerpts() -> str:
    """A few characteristic lines from both projects (local paths and host name removed)."""
    picks = [
        (
            RAW / "tier3" / "pq.gnb.log",
            ["UERANSIM v", "NG Setup procedure is successful", "Initial NAS message received"],
        ),
        (
            RAW / "tier3" / "pq.ue.log",
            [
                "UERANSIM v",
                "[SUCI] scheme=12",
                "Initial Registration is successful",
                "PDU Session establishment is successful",
                "TUN interface[uesimtun0",
            ],
        ),
        (
            ROOT / "runtime" / "log" / "amf.log",
            ["Open5GS daemon v", "InitialUEMessage", "Registration request"],
        ),
        (
            ROOT / "runtime" / "log" / "udm.log",
            ["Open5GS daemon v", "ML-KEM-768 secret key loaded", "[SIDF] scheme=12"],
        ),
    ]
    # Core logs are appended across runs: take the lines from the same second as the
    # scheme 12 SUCI in the UE log (version banners and key loading from anywhere).
    ue_log = (RAW / "tier3" / "pq.ue.log").read_text(errors="replace")
    stamp = re.search(r"(\d\d:\d\d:\d\d)\.\d+\] \[nas\] \[info\] \[SUCI\]", ue_log)
    second = stamp.group(1) if stamp else ""
    out = []
    for path, needles in picks:
        if not path.exists():
            continue
        lines = path.read_text(errors="replace").splitlines()
        out.append(f"== {path.name.replace('pq.', 'UERANSIM ')}")
        for needle in needles:
            anywhere = needle.startswith(("UERANSIM v", "Open5GS daemon", "ML-KEM"))
            hit = next(
                (ln for ln in lines if needle in ln and (anywhere or second in ln)),
                next((ln for ln in lines if needle in ln), None),
            )
            if hit:
                hit = hit.replace(str(ROOT) + "/", "")
                hit = re.sub(r"supi=imsi-\d+", "supi=imsi-999700000000001", hit)
                out.append(hit[:150])
    return "\n".join(out) + "\n"


def packet_list(pcap: Path, nfs: dict[str, str]) -> list[dict[str, object]]:
    """Wireshark-style packet list of one registration (NGAP and SBI requests/responses)."""
    names = {**nfs, GNB_IP: "127.0.0.1", SCP_IP: "SCP"}
    rows = []
    for num, t, src, dst, proto, length, info in tshark(
        pcap,
        "ngap || http2.type == 1",
        [
            "frame.number",
            "frame.time_relative",
            "ip.src",
            "ip.dst",
            "_ws.col.Protocol",
            "frame.len",
            "_ws.col.Info",
        ],
    ):
        rows.append(
            {
                "no": int(num),
                "time_s": round(float(t), 6),
                "source": f"{src} ({names.get(src, '')})".replace(" ()", "").replace(
                    "127.0.0.1 (127.0.0.1)", "127.0.0.1"
                ),
                "destination": f"{dst} ({names.get(dst, '')})".replace(" ()", "").replace(
                    "127.0.0.1 (127.0.0.1)", "127.0.0.1"
                ),
                "protocol": proto,
                "length": int(length),
                "info": info.replace("|", ", ")[:110],
            }
        )
    return rows


def protocol_hierarchy(pcap: Path, scheme: str) -> list[dict[str, object]]:
    """tshark -z io,phs (protocol hierarchy statistics), one row per protocol."""
    cmd = ["tshark", "-r", str(pcap), "-d", "tcp.port==7777,http2", "-q", "-z", "io,phs"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        m = re.match(r"^(\s*)(\S+)\s+frames:(\d+)\s+bytes:(\d+)", line)
        if m:
            rows.append(
                {
                    "scheme": scheme,
                    "depth": len(m.group(1)) // 2,
                    "protocol": m.group(2),
                    "frames": int(m.group(3)),
                    "bytes": int(m.group(4)),
                }
            )
    return rows


def io_graph(pcap: Path, scheme: str, bin_ms: int = 100) -> list[dict[str, object]]:
    """Wireshark I/O graph data: NGAP and HTTP/2 packets per time bin."""
    counts: dict[tuple[int, str], int] = {}
    for t, protos in tshark(pcap, "ngap || http2", ["frame.time_relative", "frame.protocols"]):
        kind = "NGAP (N2)" if ":ngap" in protos else "HTTP/2 (SBI)"
        key = (int(float(t) * 1000 // bin_ms), kind)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"scheme": scheme, "t_ms": b * bin_ms, "series": k, "packets": n}
        for (b, k), n in sorted(counts.items())
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write rows with the keys of the first row as header."""
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows -> {path.relative_to(ROOT)}")


def main() -> None:
    """Extract everything that exists locally."""
    nfs = nf_addresses()
    write_csv(PROC / "stack_sequence.csv", sequence(RAW / "tier3" / "pq.pcap", nfs))
    rows = []
    for scheme in SCHEMES:
        pcap = RAW / "tier3" / f"{scheme}.pcap"
        if pcap.exists():
            rows += interface_bytes(pcap, scheme, nfs)
    write_csv(PROC / "stack_interface_bytes.csv", rows)
    write_csv(PROC / "stack_ue_events.csv", [e for s in SCHEMES for e in ue_events(s)])
    storm = []
    for scheme in SCHEMES:
        pcap = RAW / "e4" / "pq" / scheme / "n100" / "rep_1.pcap"
        if pcap.exists():
            storm += storm_progress(pcap, scheme)
    write_csv(PROC / "stack_storm_progress.csv", storm)
    write_csv(PROC / "wireshark_packet_list.csv", packet_list(RAW / "tier3" / "pq.pcap", nfs))
    phs = []
    for scheme in SCHEMES:
        pcap = RAW / "tier3" / f"{scheme}.pcap"
        if pcap.exists():
            phs += protocol_hierarchy(pcap, scheme)
    write_csv(PROC / "wireshark_protocol_hierarchy.csv", phs)
    io_rows = []
    for scheme in SCHEMES:
        pcap = RAW / "e4" / "pq" / scheme / "n100" / "rep_1.pcap"
        if pcap.exists():
            io_rows += io_graph(pcap, scheme)
    write_csv(PROC / "wireshark_io_graph.csv", io_rows)
    (RAW / "stack").mkdir(parents=True, exist_ok=True)
    (RAW / "stack" / "log_excerpts.txt").write_text(log_excerpts())
    print("log excerpts -> results/raw/stack/log_excerpts.txt")


if __name__ == "__main__":
    main()
