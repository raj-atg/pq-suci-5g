"""Figures for the full-stack (Open5GS + UERANSIM) capture experiments.

Writes results/figures/fig10..fig18 {png, pdf, txt}. Inputs are the stack_*.csv and
wireshark_*.csv files in results/processed plus results/raw/stack/log_excerpts.txt and
the Open5GS configs. Each figure function skips when its input is missing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

from make_figures import (
    INK,
    MUTED,
    RAW,
    ROOT,
    load,
    save,
    style,
)

HILITE = "#D55E00"  # vermillion: SUCI-carrying path
CONF = ROOT / "config" / "open5gs"
SCHEMES = ["null", "profile-a", "profile-b", "mlkem768"]
SBI_RE = re.compile(r"sbi:\s*\n\s*server:\s*\n\s*- address: (\S+)")


def sbi_addresses() -> dict[str, str]:
    """Read each NF's SBI listen address from config/open5gs/<nf>.yaml (skips *-pq.yaml)."""
    out: dict[str, str] = {}
    for path in sorted(CONF.glob("*.yaml")):
        if path.stem.endswith("-pq"):
            continue
        m = SBI_RE.search(path.read_text(encoding="utf-8"))
        if m:
            out[path.stem.upper()] = m.group(1)
    return out


def upf_address() -> str:
    """Read the UPF GTP-U/PFCP address from upf.yaml."""
    text = (CONF / "upf.yaml").read_text(encoding="utf-8")
    m = re.search(r"gtpu:\s*\n\s*server:\s*\n\s*- address: (\S+)", text)
    return m.group(1) if m else "127.0.0.7"


# ---------------------------------------------------------------- fig10 testbed


def _box(
    ax: Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    sub: str = "",
    fc: str = "white",
    ec: str = INK,
    lw: float = 1.2,
    fs: float = 9,
) -> None:
    """Draw a rounded box with a bold title and an optional smaller second line."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0,rounding_size=1.2",
            facecolor=fc,
            edgecolor=ec,
            linewidth=lw,
            zorder=2,
        )
    )
    if sub:
        ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", fontsize=fs, zorder=3)
        ax.text(
            x + w / 2,
            y + h * 0.28,
            sub,
            ha="center",
            va="center",
            fontsize=fs - 2,
            color=MUTED,
            family="monospace",
            zorder=3,
        )
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=fs, zorder=3)
    ax.texts[-1 if not sub else -2].set_fontweight("bold")


def _link(
    ax: Axes,
    p: tuple[float, float],
    q: tuple[float, float],
    color: str = MUTED,
    lw: float = 1.4,
    arrow: str = "<->",
    ls: str = "-",
    z: int = 1,
) -> None:
    """Draw a straight link between two points."""
    ax.annotate(
        "",
        xy=q,
        xytext=p,
        arrowprops={"arrowstyle": arrow, "color": color, "lw": lw, "ls": ls},
        zorder=z,
    )


def _tag(ax: Axes, x: float, y: float, text: str, color: str = INK, fs: float = 7.5) -> None:
    """Small centered label with a white background."""
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=fs,
        color=color,
        zorder=6,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2},
    )


def _nf(ax: Axes, x: float, y: float, w: float, h: float, name: str, ip: str, hot: bool) -> None:
    """Draw a small gray NF box (name and IP only)."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8",
            facecolor="#EDEDED", edgecolor="#A8A8A8", linewidth=1, zorder=2,
        )
    )  # fmt: skip
    ax.text(x + w / 2, y + h * 0.62, name, ha="center", va="center", fontsize=9, color=MUTED)
    ax.text(x + w / 2, y + h * 0.22, ip, ha="center", va="center", fontsize=6, color=MUTED)


def fig10_testbed() -> None:
    """Simple architecture diagram: SUCI path and the UPF/SMF in color, rest gray."""
    ip = sbi_addresses()
    if not ip:
        print("skip: fig10 no config/open5gs yaml")
        return
    upf = upf_address()
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 145)
    ax.set_ylim(0, 76)
    ax.axis("off")
    ax.grid(False)
    ax.add_patch(Rectangle((1, 8), 28, 64, facecolor="#F4F4F4", edgecolor=MUTED, lw=1.4, zorder=0))
    ax.text(15, 68.5, "UERANSIM v3.3.0", ha="center", fontsize=13, fontweight="bold")
    ax.add_patch(Rectangle((46, 8), 98, 64, facecolor="#F4F4F4", edgecolor=MUTED, lw=1.4, zorder=0))
    ax.text(95, 68.5, "Open5GS v2.8.0 (5G SA core)", ha="center", fontsize=13, fontweight="bold")
    hot_fc = "#FDEBDD"
    _box(ax, 4, 46, 22, 12, "UE", "SUCI here", fc=hot_fc, ec=HILITE, lw=2.2, fs=13)
    _box(ax, 4, 24, 22, 12, "gNB", "127.0.0.1", fc=hot_fc, ec=HILITE, lw=2.2, fs=13)
    _link(ax, (15, 46), (15, 36), color=HILITE, lw=2.6, arrow="->", z=5)
    _tag(ax, 15, 41, "RLS", HILITE, 10)
    bus_y = 42.0
    for i, (nf, title) in enumerate((("AMF", "AMF"), ("AUSF", "AUSF"), ("UDM", "UDM+SIDF"))):
        x = 52 + 22 * i
        _box(ax, x, 50, 17, 12, title, ip.get(nf, ""), fc=hot_fc, ec=HILITE, lw=2.2, fs=13)
        ax.plot([x + 8.5] * 2, [50, bus_y], color=MUTED, lw=1.6, zorder=1)
    for a, b in ((52, 74), (74, 96)):
        _link(ax, (a + 17, 56), (b, 56), color=HILITE, lw=2.6, arrow="->", z=5)
    _box(ax, 52, 24, 17, 12, "SMF", ip.get("SMF", ""), fs=13, lw=1.6)
    ax.plot([60.5] * 2, [36, bus_y], color=MUTED, lw=1.6, zorder=1)
    ax.plot([60.5, 133], [bus_y] * 2, color=MUTED, lw=3.4, zorder=1)
    _tag(ax, 139, bus_y, "SBI", INK, 12)
    gray = ["SCP", "NRF", "UDR", "PCF", "NSSF", "BSF"]
    for i, nf in enumerate(gray):
        x = 74 + 10.5 * i
        _nf(ax, x, 30, 9.5, 7, nf, ip.get(nf, ""), False)
        ax.plot([x + 4.75] * 2, [37, bus_y], color="#B8B8B8", lw=1.2, zorder=1)
    _nf(ax, 118, 14, 18, 7, "MongoDB", "127.0.0.1:27017", False)
    _box(ax, 52, 10, 17, 10, "UPF", upf, fs=13, lw=1.6)
    _link(ax, (60.5, 24), (60.5, 20), arrow="<->", lw=2.0)
    _tag(ax, 66, 22, "N4", INK, 12)
    _nf(ax, 88, 12, 16, 7, "ogstun", "10.45.0.1/16", False)
    _link(ax, (69, 15), (88, 15), arrow="->", lw=2.0)
    _tag(ax, 78.5, 17, "N6", INK, 11)
    _link(ax, (26, 33), (52, 56), color=HILITE, lw=3.0, arrow="->", z=5)
    _tag(ax, 36, 45.5, "N2", HILITE, 13)
    _link(ax, (26, 27), (52, 14), arrow="<->", lw=2.0)
    _tag(ax, 36, 21, "N3", INK, 13)
    ax.text(
        72, 3, "All on one Linux host (WSL2), loopback addresses; captures taken on lo with tshark",
        ha="center", fontsize=10, style="italic", color=MUTED,
    )  # fmt: skip
    ax.legend(
        handles=[Line2D([], [], color=HILITE, lw=3, label="SUCI path")],
        loc="lower right", bbox_to_anchor=(1.0, 0.0), fontsize=11,
    )  # fmt: skip
    ax.set_title("Testbed: UERANSIM and Open5GS (ML-KEM SUCI on liboqs 0.16.0)", fontsize=14)
    save(
        fig,
        "fig10_testbed",
        "Deployed testbed: UERANSIM v3.3.0 (UE and gNB) in front of an Open5GS v2.8.0 5G SA "
        "core, all on one host with SBI addresses read from config/open5gs. The vermillion path "
        "is the one the SUCI takes from the UE to the SIDF in the UDM; the SMF and UPF are shown "
        "for the user plane and the remaining NFs in gray.",
    )


# ---------------------------------------------------------------- fig11 sequence

LIFELINES = ["gNB", "AMF", "AUSF", "UDM", "UDR", "PCF", "BSF", "SMF"]


def fig11_message_sequence() -> None:
    """Message sequence of the registration part of one scheme 12 run."""
    df = load("stack_sequence.csv")
    if df is None:
        return
    df["carries_suci"] = df["carries_suci"].astype(str).str.lower() == "true"
    stop = df.index[df["label"] == "InitialContextSetup"]
    if len(stop):
        df = df.loc[: stop[0]]
    used = set(df["src"]) | set(df["dst"])
    lanes = [n for n in LIFELINES if n in used]
    xs = {n: float(i) for i, n in enumerate(lanes)}
    n = len(df)
    fig, ax = plt.subplots(figsize=(11, 9.5))
    ax.set_xlim(-1.0, len(lanes) - 0.4)
    ax.set_ylim(n + 0.2, -2.0)
    ax.axis("off")
    for lane in lanes:
        ax.plot([xs[lane]] * 2, [-0.4, n - 0.4], color="#C8C8C8", lw=1.2, zorder=0)
        ax.text(xs[lane], -1.0, lane, ha="center", va="center", fontweight="bold", fontsize=14)
    for i, row in enumerate(df.itertuples()):
        hot = bool(row.carries_suci)
        color = HILITE if hot else MUTED
        x1, x2 = xs[row.src], xs[row.dst]
        ax.annotate(
            "", xy=(x2, i), xytext=(x1, i),
            arrowprops={"arrowstyle": "->", "color": color, "lw": 2.6 if hot else 1.4},
        )  # fmt: skip
        ax.text(-1.0, i, f"{float(row.t_ms):,.0f} ms", ha="left", va="center", fontsize=10,
                color=MUTED)  # fmt: skip
        label = str(row.label).split(" ")[0]
        ax.text(
            (x1 + x2) / 2, i - 0.12, label, ha="center", va="bottom", fontsize=11,
            color=color, fontweight="bold" if hot else "normal", zorder=3,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.3, "alpha": 0.85},
        )  # fmt: skip
    ax.legend(
        handles=[
            Line2D([], [], color=HILITE, lw=2.6, label="carries the SUCI"),
            Line2D([], [], color=MUTED, lw=1.4, label="other messages"),
        ],
        loc="lower right", fontsize=11,
    )  # fmt: skip
    ax.set_title("One scheme 12 registration through Open5GS (from a real capture)", fontsize=14)
    save(
        fig,
        "fig11_message_sequence",
        f"The first {n} messages of one scheme 12 registration, up to the InitialContextSetup "
        "that completes it, reconstructed from a tshark capture; later PDU session messages are "
        "not shown. Rows are ordered by message, not by time, with the capture time at the left. "
        "SBI requests pass through the SCP (omitted for clarity) and only requests are shown.",
    )


# ---------------------------------------------------------------- fig12 bytes


def fig12_interface_bytes() -> None:
    """Profile A versus scheme 12 payload bytes on the six largest interfaces."""
    df = load("stack_interface_bytes.csv")
    if df is None:
        return
    df = df[df["interface"] != "SBI NRF"]
    piv = df.pivot(index="interface", columns="scheme", values="payload_bytes")
    top = piv[["profile-a", "mlkem768"]].max(axis=1).nlargest(6).index
    sub = piv.loc[top].sort_values("mlkem768", ascending=False)
    ifaces = list(sub.index)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    h = 0.38
    for j, (k, color, lab) in enumerate(
        (("profile-a", "#8C8C8C", "Profile A (1)"), ("mlkem768", HILITE, "Scheme 12 (ML-KEM-768)"))
    ):
        pos = [i + (j - 0.5) * h for i in range(len(ifaces))]
        vals = sub[k].to_numpy()
        ax.barh(pos, vals, h * 0.94, color=color, label=lab)
        for p, v in zip(pos, vals, strict=True):
            ax.text(v + 80, p, f"{v:,.0f}", va="center", fontsize=11)
    ax.set_yticks(range(len(ifaces)))
    ax.set_yticklabels(ifaces, fontsize=12)
    ax.invert_yaxis()
    ax.set_xlabel("Payload bytes per registration", fontsize=12)
    ax.tick_params(axis="x", labelsize=11)
    ax.set_xlim(right=ax.get_xlim()[1] * 1.12)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=11)
    ax.set_title("Bytes per interface: Profile A vs scheme 12", fontsize=14)
    fig.tight_layout()
    grow = [i for i in ("N2 gNB-AMF", "SBI AUSF", "SBI UDM") if i in piv.index]
    parts = [f"{i} +{piv.loc[i, 'mlkem768'] - piv.loc[i, 'profile-a']:,.0f} B" for i in grow]
    save(
        fig,
        "fig12_interface_bytes",
        "Application payload bytes per interface for one registration, Profile A versus scheme "
        "12, on the six largest interfaces (stack_interface_bytes.csv). Increases from Profile A "
        f"to scheme 12: {'; '.join(parts)}. SBI NRF is excluded because NRF heartbeats vary "
        "between runs.",
    )


# ---------------------------------------------------------------- fig13 timeline


def fig13_ue_gnb_timeline() -> None:
    """Phases of one scheme 12 registration as seen by the UERANSIM UE (one bar)."""
    df = load("stack_ue_events.csv")
    if df is None:
        return
    ev = df[(df["scheme"] == "mlkem768") & (df["component"] == "UE")]

    def at(text: str) -> float:
        return float(ev[ev["event"].str.contains(text, regex=False)]["t_ms"].min())

    marks = [
        ("UE start", 0.0),
        ("request sent", at("RRC-CONNECTED")),
        ("Registration\naccepted", at("Registration accept received")),
        ("PDU session\nestablished", at("PDU Session establishment is successful")),
        ("uesimtun0 up", at("TUN uesimtun")),
    ]
    phases = ["", "Core: authentication and registration", "PDU session", "Tunnel"]
    shades = [HILITE, "#8C8C8C", "#B5B5B5", "#D9D9D9"]
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.grid(False)
    for i, (name, color) in enumerate(zip(phases, shades, strict=True)):
        a, b = marks[i][1], marks[i + 1][1]
        ax.barh(0, max(b - a, 2), left=a, height=0.45, color=color, edgecolor="white")
        if name:
            ax.text((a + b) / 2, 0.3, name, ha="center", va="bottom", fontsize=10.5)
    ax.annotate(
        "UE: SUCI computed\nand request sent",
        xy=(marks[1][1] / 2, 0.22),
        xytext=(marks[1][1] + 25, 0.62),
        fontsize=10.5,
        color=HILITE,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": HILITE, "lw": 1},
    )
    for label, t in marks[1:]:
        ax.vlines(t, -0.24, 0.24, color="#333333", lw=0.9)
        ax.text(t, -0.3, f"{label}\n{t:.0f} ms", ha="center", va="top", fontsize=9.5)
    ax.set_ylim(-0.95, 0.95)
    ax.set_yticks([])
    ax.set_xlim(0, marks[-1][1] * 1.05)
    ax.set_xlabel("Time since the UERANSIM UE started (ms)", fontsize=11)
    ax.set_title("One scheme 12 registration seen by the UERANSIM UE", fontsize=13)
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    suci_ms = at("SUCI computed")
    save(
        fig,
        "fig13_ue_gnb_timeline",
        "Phases of one scheme 12 registration from the UERANSIM UE log (stack_ue_events.csv). "
        f"The UE computed the post-quantum SUCI {suci_ms:.0f} ms after start; almost all of the "
        f"time until the Registration Accept ({marks[2][1]:.0f} ms) is spent in the core and in "
        "protocol timers, not in the SUCI.",
    )


def fig14_storm_progress() -> None:
    """Cumulative registered UEs during the 100-UE storm, Profile A versus scheme 12."""
    df = load("stack_storm_progress.csv")
    if df is None:
        return
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    done = []
    for k, color, lab in (
        ("profile-a", "#8C8C8C", "Profile A (1)"),
        ("mlkem768", HILITE, "Scheme 12 (ML-KEM-768)"),
    ):
        g = df[df["scheme"] == k].sort_values("t_ms")
        if g.empty:
            continue
        # start each curve at (0, 0): time 0 is the first InitialUEMessage of the storm
        x = np.concatenate([[0.0], g["t_ms"].to_numpy() / 1000])
        y = np.concatenate([[0], g["registered_ues"].to_numpy()])
        ax.step(x, y, where="post", color=color, lw=2.2, label=lab)
        done.append(f"{lab} {g['t_ms'].max() / 1000:.2f} s")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Time since the first UE started registering (s)", fontsize=12)
    ax.set_ylabel("UEs registered", fontsize=12)
    ax.tick_params(labelsize=11)
    ax.legend(loc="lower right", fontsize=11)
    ax.set_title("100 UEs registering at once", fontsize=13)
    fig.tight_layout()
    save(
        fig,
        "fig14_storm_progress",
        "Number of UEs that completed registration (reached InitialContextSetupRequest) over "
        "time when UERANSIM starts 100 UEs at once (`nr-ue -n 100`) against Open5GS. Markers "
        "from NGAP in the tshark capture (stack_storm_progress.csv, repetition 1). The first "
        "UE needs a few hundred ms because all registrations arrive together. Last UE "
        f"registered after: {'; '.join(done)}.",
    )


# ---------------------------------------------------------------- fig15 logs

LOG_TITLES = {
    "UERANSIM gnb.log": "UERANSIM nr-gnb log",
    "UERANSIM ue.log": "UERANSIM nr-ue log",
    "amf.log": "Open5GS AMF log",
    "udm.log": "Open5GS UDM log",
}
HOT_RE = re.compile(r"\[SUCI\]|\[SIDF\]|ML-KEM")


def _parse_sections(path: Path) -> list[tuple[str, list[str]]]:
    """Split log_excerpts.txt on '== name' headers."""
    secs: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("== "):
            name = line[3:].strip()
            secs.append((LOG_TITLES.get(name, name), []))
        elif secs and line.strip():
            secs[-1][1].append(line)
    return secs


def fig15_log_evidence() -> None:
    """Text figure of log lines showing the SUCI and SIDF events."""
    path = RAW / "stack" / "log_excerpts.txt"
    if not path.exists():
        print("skip: log_excerpts.txt missing")
        return
    secs = _parse_sections(path)
    nrows = sum(len(ls) + 2 for _, ls in secs)
    fig, ax = plt.subplots(figsize=(14, 0.2 * nrows + 0.8))
    ax.set_xlim(0, 120)
    ax.set_ylim(nrows, 0)
    ax.axis("off")
    y = 0.5
    for title, lines in secs:
        ax.text(0, y + 0.5, title, fontsize=9.5, fontweight="bold", va="center")
        y += 1.4
        for ln in lines:
            text = ln if len(ln) <= 120 else ln[:117] + "..."
            if HOT_RE.search(ln):
                ax.add_patch(
                    Rectangle((-0.5, y - 0.45), 121, 0.95, facecolor="#FFE9B8", edgecolor="none")
                )
            ax.text(0, y, text, family="monospace", fontsize=7.2, va="center")
            y += 1.0
        y += 0.6
    save(
        fig,
        "fig15_log_evidence",
        "Excerpts of the UERANSIM and Open5GS logs for one scheme 12 registration, taken from "
        "results/raw/stack/log_excerpts.txt. Highlighted lines show the UE concealing the SUCI "
        "and the UDM SIDF deconcealing it with ML-KEM-768; lines are truncated to 120 characters.",
    )


# ---------------------------------------------------------------- fig16 packet list


def fig16_wireshark_packet_list() -> None:
    """Wireshark-style packet list table (first 20 rows)."""
    df = load("wireshark_packet_list.csv")
    if df is None:
        return
    df = df.head(20)
    cols = [("No.", 5), ("Time", 10), ("Source", 20), ("Destination", 20), ("Protocol", 14),
            ("Length", 8), ("Info", 62)]  # fmt: skip
    total = sum(w for _, w in cols)
    fig, ax = plt.subplots(figsize=(total * 0.0775, 0.27 * (len(df) + 2) + 0.7))
    fig.subplots_adjust(left=0.003, right=0.997)
    ax.set_xlim(0, total)
    ax.set_ylim(len(df) + 1.5, -1.2)
    ax.axis("off")
    xs = np.cumsum([0] + [w for _, w in cols])
    ax.add_patch(Rectangle((0, -0.5), total, 1, facecolor="#E8E8E8", edgecolor=MUTED))
    for (name, _), x in zip(cols, xs, strict=False):
        ax.text(x + 0.5, 0, name, family="monospace", fontsize=9.5, fontweight="bold", va="center")
    hot_re = re.compile(r"suci-0-|InitialUEMessage|ue-authentications")
    for i, r in enumerate(df.itertuples(), start=1):
        proto, info = str(r.protocol), str(r.info)
        hot = bool(hot_re.search(info))
        base = "#E3ECF6" if "NGAP" in proto else "#F1F1F1"
        if hot:
            base = "#FFD9B8"
        ax.add_patch(
            Rectangle(
                (0, i - 0.5), total, 1, facecolor=base,
                edgecolor=HILITE if hot else "none", lw=2.0 if hot else 0,
                zorder=2 if hot else 1,
            )
        )  # fmt: skip
        proto = proto.replace("/NAS-5GS", "")
        vals = [r.no, f"{r.time_s:.6f}", r.source, r.destination, proto, r.length]
        vals.append(info if len(info) <= 60 else info[:57] + "...")
        for v, x in zip(vals, xs, strict=False):
            ax.text(
                x + 0.5, i, str(v), family="monospace", fontsize=9, va="center", zorder=3,
                fontweight="bold" if hot else "normal",
            )  # fmt: skip
    ax.set_title(
        "tshark packet list: scheme 12 registration on the loopback interface", fontsize=13
    )
    save(
        fig,
        "fig16_wireshark_packet_list",
        f"First {len(df)} packets of a scheme 12 registration captured on lo, in the style of "
        "the Wireshark packet list (wireshark_packet_list.csv). Orange rows carry the SUCI "
        "(InitialUEMessage and the SBI requests whose URI contains it); blue rows are NGAP and "
        "gray rows are HTTP/2. The Info column is truncated to 60 characters.",
    )


# ---------------------------------------------------------------- fig17 hierarchy


def _shallow_bytes(g: pd.DataFrame, proto: str) -> float:
    """Sum bytes of rows at the shallowest depth where the protocol appears."""
    r = g[g["protocol"] == proto]
    if r.empty:
        return float("nan")
    return float(r[r["depth"] == r["depth"].min()]["bytes"].sum())


def fig17_protocol_hierarchy() -> None:
    """NGAP and HTTP/2 bytes, Profile A versus scheme 12, from tshark -z io,phs."""
    df = load("wireshark_protocol_hierarchy.csv")
    if df is None:
        return
    protos = [("ngap", "NGAP (N2)"), ("http2", "HTTP/2 (SBI)")]
    vals = {
        k: {p: _shallow_bytes(df[df["scheme"] == k], p) for p, _ in protos}
        for k in ("profile-a", "mlkem768")
    }
    fig, axes = plt.subplots(1, 2, figsize=(8, 4.6))
    for ax, (p, name) in zip(axes, protos, strict=True):
        v = [vals["profile-a"][p], vals["mlkem768"][p]]
        bars = ax.bar([0, 1], v, 0.6, color=["#8C8C8C", HILITE])
        for b, y in zip(bars, v, strict=True):
            ax.text(b.get_x() + b.get_width() / 2, y, f"{y:,.0f}", ha="center", va="bottom",
                    fontsize=12)  # fmt: skip
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Profile A", "Scheme 12"], fontsize=12)
        ax.set_title(name, fontsize=14)
        ax.set_ylim(0, max(v) * 1.15)
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="y", labelsize=11)
    axes[0].set_ylabel("Bytes per registration capture", fontsize=12)
    fig.tight_layout()
    d = vals["mlkem768"]["ngap"] - vals["profile-a"]["ngap"]
    save(
        fig,
        "fig17_protocol_hierarchy",
        "Bytes per protocol from `tshark -z io,phs` on one registration capture per scheme "
        "(wireshark_protocol_hierarchy.csv), Profile A versus scheme 12; the two panels use "
        "separate y axes. The HTTP/2 totals also include NRF heartbeat traffic, which varies "
        f"between runs, so only the NGAP difference is clean here ({d:+,.0f} B for scheme 12).",
    )


# ---------------------------------------------------------------- fig18 io graph


def fig18_io_graph() -> None:
    """NGAP packets per 100 ms during the 100-UE storm, Profile A versus scheme 12."""
    df = load("wireshark_io_graph.csv")
    if df is None:
        return
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    totals = []
    for k, color, lab in (
        ("profile-a", "#8C8C8C", "Profile A (1)"),
        ("mlkem768", HILITE, "Scheme 12 (ML-KEM-768)"),
    ):
        g = df[(df["scheme"] == k) & (df["series"] == "NGAP (N2)")]
        grid = np.arange(0, int(df[df["scheme"] == k]["t_ms"].max()) + 100, 100)
        ser = g.set_index("t_ms")["packets"].reindex(grid, fill_value=0)
        ax.plot(grid / 1000, ser.to_numpy(), color=color, lw=2.2, label=lab)
        totals.append(f"{lab} {int(g['packets'].sum()):,}")
    ax.set_xlabel("Time (s)", fontsize=12)
    ax.set_ylabel("NGAP packets per 100 ms", fontsize=12)
    ax.tick_params(labelsize=11)
    ax.legend(loc="upper left", fontsize=11)
    ax.set_title("N2 packet rate during the 100-UE storm", fontsize=14)
    fig.tight_layout()
    save(
        fig,
        "fig18_io_graph",
        "Wireshark-style I/O graph of the 100-UE registration storms: NGAP (N2) packets per "
        "100 ms bin for Profile A and scheme 12, from wireshark_io_graph.csv; empty bins are "
        f"drawn as zero. Total NGAP packets in the capture: {'; '.join(totals)}.",
    )


FIGURES: list[Callable[[], None]] = [
    fig10_testbed,
    fig11_message_sequence,
    fig12_interface_bytes,
    fig13_ue_gnb_timeline,
    fig14_storm_progress,
    fig15_log_evidence,
    fig16_wireshark_packet_list,
    fig17_protocol_hierarchy,
    fig18_io_graph,
]


def main() -> None:
    """Generate the stack figures."""
    style()
    for fn in FIGURES:
        fn()


if __name__ == "__main__":
    main()
