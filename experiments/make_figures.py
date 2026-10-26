"""Build report figures from results/processed/*.csv.

Writes results/figures/figN_<name>.{png,pdf,txt}. Every figure function skips
with a message when its input CSV is missing or empty, so the script can be
re-run while experiments are still producing data.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "results" / "processed"
RAW = ROOT / "results" / "raw"
OUT = ROOT / "results" / "figures"

# Canonical scheme key -> (label, color). Okabe-Ito colorblind-safe palette.
LABELS: dict[str, str] = {
    "null": "Null (0)",
    "profile-a": "Profile A (1)",
    "profile-b": "Profile B (2)",
    "mlkem512": "ML-KEM-512*",
    "mlkem768": "ML-KEM-768 (12)",
    "mlkem1024": "ML-KEM-1024*",
    "hybrid": "Hybrid X25519+ML-KEM-768 (13)",
}
COLORS: dict[str, str] = {
    "null": "#8C8C8C",
    "profile-a": "#0072B2",
    "profile-b": "#E69F00",
    "mlkem512": "#56B4E9",
    "mlkem768": "#009E73",
    "mlkem1024": "#D55E00",
    "hybrid": "#CC79A7",
}
ORDER: list[str] = list(LABELS)
ALIASES: dict[str, str] = {
    "profilea": "profile-a",
    "profileb": "profile-b",
    "pq": "mlkem768",
}
BENCH_NOTE = "Schemes marked * are benchmark only (no standardized scheme ID)."
INK = "#222222"
MUTED = "#6B6B6B"


def canon(name: str) -> str:
    """Map a CSV scheme value to its canonical key."""
    key = str(name).strip().lower()
    return ALIASES.get(key, key)


def style() -> None:
    """Apply the shared minimal matplotlib style."""
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#E3E3E3",
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def load(name: str) -> pd.DataFrame | None:
    """Read a processed CSV with canonical scheme names, or None if unusable."""
    path = PROC / name
    if not path.exists():
        print(f"skip: {name} missing")
        return None
    df = pd.read_csv(path, keep_default_na=False, na_values=[""])
    if df.empty:
        print(f"skip: {name} empty")
        return None
    if "scheme" in df.columns:
        df["scheme"] = df["scheme"].map(canon)
    return df


def save(fig: Figure, stem: str, caption: str) -> None:
    """Write PNG (300 dpi), PDF and the caption text file."""
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    (OUT / f"{stem}.txt").write_text(caption.strip() + "\n", encoding="utf-8")
    plt.close(fig)
    print(f"ok: {stem}")


def present(keys: list[str], df: pd.DataFrame) -> list[str]:
    """Return keys (in canonical order) that appear in df['scheme']."""
    have = set(df["scheme"])
    return [k for k in ORDER if k in keys and k in have]


def scheme_legend(ax: Axes, keys: list[str], **kw: object) -> None:
    """Add a color legend for the given schemes."""
    handles = [Patch(color=COLORS[k], label=LABELS[k]) for k in keys]
    ax.legend(handles=handles, **kw)  # type: ignore[arg-type]


def pick_core(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Prefer rows with core == pq, else stock."""
    if "pq" in set(df["core"]):
        return df[df["core"] == "pq"], "pq"
    return df[df["core"] == "stock"], "stock"


def fig1_sizes() -> None:
    """Scheme output bytes and SUCI string length per scheme."""
    df = load("e2_sizes_computed.csv")
    if df is None:
        return
    keys = present(ORDER, df)
    df = df.set_index("scheme").loc[keys]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    cols = [
        ("scheme_output_bytes", "Scheme output (bytes)"),
        ("suci_string_chars", "SUCI string length (characters)"),
    ]
    for ax, (col, ylabel) in zip(axes, cols, strict=True):
        vals = df[col].to_numpy()
        bars = ax.bar(range(len(keys)), vals, color=[COLORS[k] for k in keys])
        ax.set_yscale("log")
        ax.set_ylim(top=vals.max() * 3)
        ax.set_ylabel(ylabel)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels([LABELS[k] for k in keys], rotation=40, ha="right")
        ax.grid(axis="x", visible=False)
        for b, v in zip(bars, vals, strict=True):
            ax.annotate(
                f"{v:,.0f}",
                (b.get_x() + b.get_width() / 2, v),
                ha="center",
                va="bottom",
                fontsize=8,
                xytext=(0, 2),
                textcoords="offset points",
            )
    fig.suptitle("SUCI size by protection scheme")
    fig.tight_layout()
    save(
        fig,
        "fig1_sizes",
        "Size of the concealed SUPI field (left, bytes) and of the SUCI string "
        "(right, characters) for each protection scheme, on a log scale, taken "
        f"from e2_sizes_computed.csv. {BENCH_NOTE}",
    )


def _err(med: pd.Series, p95: pd.Series) -> np.ndarray:
    """Asymmetric error bars from median to p95."""
    return np.vstack([np.zeros(len(med)), np.clip(p95 - med, 0, None)])


def _native_panel(ax: Axes, e6: pd.DataFrame) -> None:
    """In-stack native conceal/deconceal medians with p95 bars."""
    keys = present(ORDER[1:], e6)
    sides = [("ue_conceal", "UE conceal"), ("sidf_deconceal", "SIDF deconceal")]
    w = 0.8 / max(len(keys), 1)
    for i, k in enumerate(keys):
        sub = e6[e6["scheme"] == k].set_index("side")
        xs, med, p95 = [], [], []
        for j, (s, _) in enumerate(sides):
            if s in sub.index:
                xs.append(j + (i - (len(keys) - 1) / 2) * w)
                med.append(float(sub.loc[s, "median_us"]))
                p95.append(float(sub.loc[s, "p95_us"]))
        m = pd.Series(med)
        ax.bar(
            xs,
            m,
            w * 0.92,
            color=COLORS[k],
            yerr=_err(m, pd.Series(p95)),
            capsize=2,
            error_kw={"lw": 0.8, "color": INK},
        )
    ax.set_yscale("log")
    ax.set_xticks(range(len(sides)))
    ax.set_xticklabels([s[1] for s in sides])
    ax.set_ylabel("Median time (us), bar to p95")
    ax.set_title("Native C/C++ in UERANSIM and Open5GS")
    ax.grid(axis="x", visible=False)


def fig2_compute() -> None:
    """Python conceal/deconceal and native liboqs/in-stack timings."""
    py = load("e1_micro_python.csv")
    nat = load("e1_native_liboqs.csv")
    if py is None:
        return
    e6 = load("e6_native_timings.csv")
    ncols = 2 + (e6 is not None)
    fig, axes = plt.subplots(1, ncols, figsize=(4.6 * ncols, 4.4))
    ax = axes[0]
    keys = present(ORDER[1:], py)
    ops = ["conceal", "deconceal"]
    w = 0.38
    for i, k in enumerate(keys):
        for j, op in enumerate(ops):
            row = py[(py["scheme"] == k) & (py["operation"] == op)]
            if row.empty:
                continue
            med, p95 = row["median_us"], row["p95_us"]
            ax.bar(
                i + (j - 0.5) * w,
                med.iloc[0],
                w * 0.95,
                color=COLORS[k],
                hatch="//" if j else None,
                edgecolor="white" if j else None,
                yerr=_err(med, p95),
                capsize=2,
                error_kw={"lw": 0.8, "color": INK},
            )
    ax.set_yscale("log")
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([LABELS[k] for k in keys], rotation=40, ha="right")
    ax.set_ylabel("Median time (us), bar to p95")
    ax.set_title("Python reference")
    ax.grid(axis="x", visible=False)
    ax.legend(
        handles=[
            Patch(facecolor="#BBBBBB", label="conceal"),
            Patch(facecolor="#BBBBBB", hatch="//", edgecolor="white", label="deconceal"),
        ],
        loc="upper left",
    )
    ax.set_ylim(top=ax.get_ylim()[1] * 2.5)
    if nat is not None:
        ax = axes[1]
        nk = present(ORDER, nat)
        nops = ["keygen", "encaps", "decaps"]
        w = 0.8 / len(nk)
        for i, k in enumerate(nk):
            vals = [nat[(nat["scheme"] == k) & (nat["operation"] == o)]["mean_us"] for o in nops]
            ax.bar(
                [j + (i - (len(nk) - 1) / 2) * w for j in range(len(nops))],
                [v.iloc[0] if len(v) else np.nan for v in vals],
                w * 0.92,
                color=COLORS[k],
            )
        ax.set_xticks(range(len(nops)))
        ax.set_xticklabels(nops)
        ax.set_ylabel("Mean time (us)")
        ax.set_title("Native liboqs ML-KEM")
        ax.grid(axis="x", visible=False)
        ax.set_ylim(top=ax.get_ylim()[1] * 1.3)
        scheme_legend(ax, nk, loc="upper left")
    else:
        axes[1].set_visible(False)
    if e6 is not None:
        _native_panel(axes[2], e6)
    fig.tight_layout()
    extra = (
        " The right panel shows in-stack native timings from e6_native_timings.csv."
        if e6 is not None
        else ""
    )
    save(
        fig,
        "fig2_compute",
        "Left: median conceal (solid) and deconceal (hatched) time of the Python "
        "reference per scheme with the 95th percentile as upper error bar, from "
        "e1_micro_python.csv; null is omitted. Middle: native liboqs ML-KEM keygen, "
        f"encaps and decaps means from e1_native_liboqs.csv.{extra} Log y axes. " + BENCH_NOTE,
    )


def _box(ax: Axes, df: pd.DataFrame, col: str, keys: list[str]) -> None:
    """Box plot with jittered points per scheme."""
    rng = np.random.default_rng(0)
    for i, k in enumerate(keys):
        v = df[df["scheme"] == k][col].dropna().to_numpy()
        if len(v) == 0:
            continue
        bp = ax.boxplot(
            [v],
            positions=[i],
            widths=0.5,
            showfliers=False,
            patch_artist=True,
            medianprops={"color": INK},
        )
        bp["boxes"][0].set(facecolor=COLORS[k], alpha=0.35, edgecolor=COLORS[k])
        for part in ("whiskers", "caps"):
            for ln in bp[part]:
                ln.set_color(COLORS[k])
        ax.scatter(
            i + rng.uniform(-0.15, 0.15, len(v)),
            v,
            s=14,
            color=COLORS[k],
            edgecolor="white",
            linewidth=0.4,
            zorder=3,
        )
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([LABELS[k] for k in keys], rotation=30, ha="right")
    ax.grid(axis="x", visible=False)


def fig3_registration_latency() -> None:
    """Registration and PDU session latency per scheme (E3)."""
    df = load("e3_registration.csv")
    if df is None:
        return
    sub, core = pick_core(df)
    if sub.empty:
        print("skip: e3 has no rows for chosen core")
        return
    keys = present(["null", "profile-a", "profile-b", "mlkem768"], sub)
    both = {"stock", "pq"} <= set(df["core"]) and bool(
        set(df[df["core"] == "pq"]["scheme"]) & {"null", "profile-a"}
    )
    ncols = 3 if both else 2
    fig, axes = plt.subplots(1, ncols, figsize=(4.4 * ncols, 4.2))
    _box(axes[0], sub, "registration_ms", keys)
    axes[0].set_ylabel("Registration time (ms)")
    axes[0].set_title("Registration latency")
    _box(axes[1], sub, "session_ms", keys)
    axes[1].set_ylabel("PDU session setup time (ms)")
    axes[1].set_title("Session establishment")
    note = ""
    if both:
        ax = axes[2]
        ks = [k for k in ("null", "profile-a") if k in set(df["scheme"])]
        for i, k in enumerate(ks):
            for j, c in enumerate(("stock", "pq")):
                v = df[(df["scheme"] == k) & (df["core"] == c)]["registration_ms"]
                if v.empty:
                    continue
                pos = i + (j - 0.5) * 0.4
                bp = ax.boxplot(
                    [v],
                    positions=[pos],
                    widths=0.3,
                    showfliers=False,
                    patch_artist=True,
                    medianprops={"color": INK},
                )
                bp["boxes"][0].set(
                    facecolor=COLORS[k],
                    alpha=0.35 if j == 0 else 0.8,
                    edgecolor=COLORS[k],
                    hatch="//" if j == 0 else None,
                )
        ax.set_xticks(range(len(ks)))
        ax.set_xticklabels([LABELS[k] for k in ks])
        ax.set_ylabel("Registration time (ms)")
        ax.set_title("Stock (hatched) vs patched core")
        ax.grid(axis="x", visible=False)
        note = " Right: stock versus patched core for the schemes both can run."
    fig.tight_layout()
    save(
        fig,
        "fig3_registration_latency",
        f"Registration time (left) and PDU session setup time (middle) per scheme "
        f"for the {core} core, with box plots (median, quartiles, whiskers) and "
        f"individual runs as points, from e3_registration.csv.{note}",
    )


def fig4_storm_latency() -> None:
    """Registration latency vs number of simultaneous UEs (E4)."""
    df = load("e4_storm.csv")
    if df is None:
        return
    sub, core = pick_core(df)
    if sub.empty:
        print("skip: e4_storm has no rows for chosen core")
        return
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ns = sorted(sub["n_ues"].unique())
    for k in present(ORDER, sub):
        g = sub[sub["scheme"] == k].groupby("n_ues")["registration_ms"]
        med = g.median().reindex(ns)
        p90 = g.quantile(0.9).reindex(ns)
        ax.plot(range(len(ns)), med, "-o", color=COLORS[k], lw=2, ms=5)
        ax.plot(range(len(ns)), p90, "--", color=COLORS[k], lw=1.2)
    ax.set_xticks(range(len(ns)))
    ax.set_xticklabels([str(n) for n in ns])
    ax.set_xlabel("Simultaneous UEs")
    ax.set_ylabel("Registration time (ms)")
    ax.set_title("Registration storm latency")
    keys = present(ORDER, sub)
    handles = [Line2D([], [], color=COLORS[k], lw=2, label=LABELS[k]) for k in keys]
    handles += [
        Line2D([], [], color=MUTED, lw=2, label="median"),
        Line2D([], [], color=MUTED, lw=1.2, ls="--", label="p90"),
    ]
    ax.legend(handles=handles, loc="upper left")
    fig.tight_layout()
    save(
        fig,
        "fig4_storm_latency",
        f"Median (solid) and 90th percentile (dashed) registration time versus "
        f"the number of UEs registering together for the {core} core, pooled over "
        "repetitions, from e4_storm.csv. The x axis is categorical.",
    )


def fig5_udm_cpu() -> None:
    """UDM CPU consumed per storm and per UE (E4)."""
    df = load("e4_udm_cpu.csv")
    if df is None:
        return
    sub, core = pick_core(df)
    if sub.empty:
        print("skip: e4_udm_cpu has no rows for chosen core")
        return
    sub = sub.assign(per_ue_ms=sub["udm_cpu_s"] / sub["n_ues"] * 1000.0)
    ns = sorted(sub["n_ues"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ax, col, ylabel in (
        (axes[0], "udm_cpu_s", "UDM CPU per storm (s)"),
        (axes[1], "per_ue_ms", "UDM CPU per UE (ms)"),
    ):
        for k in present(ORDER, sub):
            g = sub[sub["scheme"] == k].groupby("n_ues")[col]
            mean = g.mean().reindex(ns)
            lo = mean - g.min().reindex(ns)
            hi = g.max().reindex(ns) - mean
            ax.errorbar(
                range(len(ns)),
                mean,
                yerr=[lo, hi],
                fmt="-o",
                ms=5,
                lw=2,
                capsize=3,
                color=COLORS[k],
                label=LABELS[k],
            )
        ax.set_xticks(range(len(ns)))
        ax.set_xticklabels([str(n) for n in ns])
        ax.set_xlabel("Simultaneous UEs")
        ax.set_ylabel(ylabel)
    axes[0].set_title("Total UDM CPU")
    axes[1].set_title("UDM CPU per registered UE")
    axes[0].legend(loc="upper left")
    fig.tight_layout()
    save(
        fig,
        "fig5_udm_cpu",
        f"CPU time consumed by the UDM (the SIDF host) per registration storm "
        f"(left) and divided by the number of UEs (right) for the {core} core. "
        "Points are means over repetitions with min to max error bars, from "
        "e4_udm_cpu.csv.",
    )


def fig6_sidf_capacity() -> None:
    """SIDF M/M/c response time vs arrival rate (E5)."""
    cap = load("e5_sidf_capacity.csv")
    sat = load("e5_sidf_saturation.csv")
    if cap is None:
        return
    impl = sorted(cap["impl"].unique())[0]
    cap = cap[cap["impl"] == impl]
    cs = [c for c in (1, 4) if c in set(cap["c"])]
    fig, axes = plt.subplots(1, len(cs), figsize=(5.2 * len(cs), 4.2), sharey=True, squeeze=False)
    for ax, c in zip(axes[0], cs, strict=True):
        for k in present(ORDER[1:], cap):
            g = cap[(cap["scheme"] == k) & (cap["c"] == c)].sort_values("arrival_rate_per_s")
            ax.plot(g["arrival_rate_per_s"], g["mean_response_ms"], color=COLORS[k], lw=2)
            if sat is not None:
                s = sat[(sat["impl"] == impl) & (sat["scheme"] == k) & (sat["c"] == c)]
                if not s.empty:
                    ax.axvline(s["saturation_rate_per_s"].iloc[0], color=COLORS[k], ls=":", lw=1.2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Arrival rate (registrations/s)")
        ax.set_title(f"{c} SIDF worker" + ("s" if c > 1 else ""))
    axes[0][0].set_ylabel("Mean response time (ms)")
    lk = present(ORDER[1:], cap)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.legend(
        handles=[Patch(color=COLORS[k], label=LABELS[k]) for k in lk],
        loc="lower center",
        ncol=3,
    )
    save(
        fig,
        "fig6_sidf_capacity",
        f"Modelled mean SIDF response time versus registration arrival rate for "
        f"1 and 4 workers, using service times measured with the {impl} "
        "implementation (e5_sidf_capacity.csv). Dotted vertical lines mark each "
        "scheme's saturation rate from e5_sidf_saturation.csv. " + BENCH_NOTE,
    )


def fig7_airtime() -> None:
    """Extra uplink airtime vs PRB grant and modulation (E5)."""
    df = load("e5_airtime.csv")
    if df is None:
        return
    df["scheme"] = df["scheme"].map(canon)
    keys = [k for k in ("mlkem768", "hybrid") if k in set(df["scheme"])]
    if not keys:
        print("skip: e5_airtime has no mlkem768/hybrid rows")
        return
    mods = list(dict.fromkeys(df.sort_values("qm")["modulation"]))
    prbs = sorted(df["prbs"].unique())
    shades = ["#9ECAE1", "#4292C6", "#08519C"]
    fig, axes = plt.subplots(
        1, len(keys), figsize=(4.8 * len(keys), 4.2), sharey=True, squeeze=False
    )
    w = 0.8 / len(mods)
    for ax, k in zip(axes[0], keys, strict=True):
        for j, m in enumerate(mods):
            vals = [
                df[(df["scheme"] == k) & (df["modulation"] == m) & (df["prbs"] == p)][
                    "extra_time_ms_vs_profile_a"
                ].iloc[0]
                for p in prbs
            ]
            xs = [i + (j - (len(mods) - 1) / 2) * w for i in range(len(prbs))]
            ax.bar(xs, vals, w * 0.92, color=shades[j % len(shades)], label=m)
        ax.set_xticks(range(len(prbs)))
        ax.set_xticklabels([str(p) for p in prbs])
        ax.set_xlabel("PRB grant")
        ax.set_title(f"{LABELS[k]} vs Profile A")
        ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel("Extra uplink time (ms)")
    axes[0][0].legend(title="Modulation", loc="upper right")
    fig.tight_layout()
    save(
        fig,
        "fig7_airtime",
        "Extra uplink airtime to carry the larger SUCI relative to Profile A, "
        "from e5_airtime.csv. Model: NR 30 kHz subcarrier spacing (0.5 ms slot), "
        "1 layer, 12 data symbols per slot, illustrative code rates, no transport "
        "block quantization, protocol headers or retransmissions (see "
        "e5_airtime_notes.txt).",
    )


def _identity_lines(path: Path, limit: int = 60) -> list[str]:
    """Read the mobile identity block, truncating long lines."""
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("UE security capability"):
            break
        out.append(line if len(line) <= limit else line[: limit - 3] + "...")
    return out


def _text_panel(ax: Axes, lines: list[str], mark: str, color: str, title: str, note: str) -> None:
    """Draw dissected lines in monospace with one highlighted row."""
    n = len(lines)
    ax.set_xlim(0, 1)
    ax.set_ylim(-2.2, n + 1.2)
    ax.axis("off")
    ax.set_title(title)
    for i, line in enumerate(lines):
        y = n - i
        if line.startswith(mark):
            ax.add_patch(
                Rectangle(
                    (0.0, y - 0.45), 1.0, 0.9, facecolor=color, alpha=0.2, edgecolor=color, lw=1.5
                )
            )
        ax.text(0.01, y, line, family="monospace", fontsize=7.2, va="center")
    ax.text(0.5, -1.2, note, ha="center", fontsize=10, color=color, fontweight="bold")


def fig9_wireshark_compare() -> None:
    """Side by side dissected mobile identity: null versus a concealed scheme."""
    left = RAW / "tier1" / "null.mobile_identity.txt"
    right_pq = RAW / "tier3" / "pq.mobile_identity.txt"
    right = right_pq if right_pq.exists() else RAW / "tier1" / "profileA.mobile_identity.txt"
    if not left.exists() or not right.exists():
        print("skip: fig9 mobile_identity text files missing")
        return
    name = "scheme 12 (ML-KEM-768)" if right == right_pq else "Profile A"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    _text_panel(
        axes[0],
        _identity_lines(left),
        "MSIN",
        "#D55E00",
        "Null scheme (0)",
        "MSIN visible in clear",
    )
    _text_panel(
        axes[1],
        _identity_lines(right),
        "Scheme output",
        "#009E73",
        f"Concealed with {name}",
        "MSIN encrypted",
    )
    fig.tight_layout()
    save(
        fig,
        "fig9_wireshark_compare",
        "Dissected 5GS mobile identity from the registration request, in the "
        "style of a Wireshark detail pane: the null scheme (left) carries the "
        f"MSIN in clear, while {name} (right) carries an encrypted scheme output "
        "field instead. Long lines are truncated. Sources: "
        f"{left.relative_to(ROOT)} and {right.relative_to(ROOT)}.",
    )


FIGURES: list[Callable[[], None]] = [
    fig1_sizes,
    fig2_compute,
    fig3_registration_latency,
    fig4_storm_latency,
    fig5_udm_cpu,
    fig6_sidf_capacity,
    fig7_airtime,
    fig9_wireshark_compare,
]


def main() -> None:
    """Generate all figures, skipping those without data."""
    style()
    for fn in FIGURES:
        fn()


if __name__ == "__main__":
    main()
