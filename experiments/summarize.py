"""Build results/processed/summary.csv: one row per scheme with the headline numbers.

Every column is computed from another CSV in results/processed/ (named in the column notes in
results/processed/summary_notes.txt), so the documentation can cite this one file.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "results" / "processed"

# scheme name in each CSV family -> one row label
SCHEMES = [
    # label, sizes/e1 name, e3/e4 name, native name, on-core label
    ("null", "null", "null", "null"),
    ("profile-a", "profile-a", "profileA", "profile-a"),
    ("profile-b", "profile-b", "profileB", "profile-b"),
    ("mlkem768 (scheme 12)", "mlkem768", "pq", "mlkem768"),
    ("hybrid (scheme 13)", "hybrid", None, None),
    ("mlkem512 (benchmark only)", "mlkem512", None, None),
    ("mlkem1024 (benchmark only)", "mlkem1024", None, None),
]
NOTES = {
    "scheme_output_bytes": "e2_sizes_computed.csv",
    "suci_string_chars": "e2_sizes_computed.csv",
    "nas_reg_request_bytes": "e3_registration.csv (median, patched core)",
    "py_conceal_us": "e1_repeatability.csv (median of 3 run medians)",
    "py_deconceal_us": "e1_repeatability.csv (median of 3 run medians)",
    "native_ue_conceal_us": "e6_native_timings.csv (median, UERANSIM in-stack)",
    "native_sidf_deconceal_us": "e6_native_timings.csv (median, Open5GS UDM in-stack)",
    "e3_registration_median_ms": "e3_registration.csv (core=pq, 30 runs)",
    "e3_registration_p95_ms": "e3_registration.csv (core=pq, 30 runs)",
    "e3_session_median_ms": "e3_registration.csv (core=pq, 30 runs)",
    "e4_100ue_registration_median_ms": "e4_storm.csv (n_ues=100, 3 reps x 100 UEs)",
    "e4_100ue_registration_p90_ms": "e4_storm.csv (n_ues=100, 3 reps x 100 UEs)",
    "e4_100ue_udm_cpu_ms_per_ue": "e4_udm_cpu.csv (n_ues=100, mean of 3 reps)",
    "e4_100ue_sessions_ok": "e4_udm_cpu.csv (n_ues=100, all reps)",
    "registered_on_core": "tier3_interop.csv (match=True on the patched core)",
}


def _read(name: str) -> pd.DataFrame:
    path = PROC / name
    return pd.read_csv(path, keep_default_na=False) if path.exists() else pd.DataFrame()


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _value(df: pd.DataFrame, col: str, **match: object) -> float | str:
    """First value of `col` in the rows matching all `match` items, or '' if none."""
    if df.empty:
        return ""
    sel = df
    for key, val in match.items():
        sel = sel[sel[key].astype(str) == str(val)]
    return "" if sel.empty else sel[col].iloc[0]


def summary_rows() -> list[dict[str, object]]:
    """Compute one summary row per scheme."""
    sizes, rep, native = (
        _read("e2_sizes_computed.csv"),
        _read("e1_repeatability.csv"),
        _read("e6_native_timings.csv"),
    )
    e3, e4, cpu, interop = (
        _read("e3_registration.csv"),
        _read("e4_storm.csv"),
        _read("e4_udm_cpu.csv"),
        _read("tier3_interop.csv"),
    )
    if not e3.empty:
        e3 = e3[e3.core == "pq"]
        for c in ("registration_ms", "session_ms", "nas_reg_request_bytes"):
            e3[c] = _num(e3[c])
    if not e4.empty:
        e4 = e4[(e4.core == "pq") & (e4.n_ues.astype(str) == "100")]
        e4 = e4.assign(registration_ms=_num(e4.registration_ms))
    if not cpu.empty:
        cpu = cpu[(cpu.core == "pq") & (cpu.n_ues.astype(str) == "100")]
    scheme_ids = {"null": "0", "profile-a": "1", "profile-b": "2", "mlkem768": "12"}

    rows = []
    for label, name, core_name, native_name in SCHEMES:
        row: dict[str, object] = {"scheme": label}
        row["scheme_output_bytes"] = _value(sizes, "scheme_output_bytes", scheme=name)
        row["suci_string_chars"] = _value(sizes, "suci_string_chars", scheme=name)
        row["py_conceal_us"] = _value(rep, "median_of_medians_us", scheme=name, operation="conceal")
        row["py_deconceal_us"] = _value(
            rep, "median_of_medians_us", scheme=name, operation="deconceal"
        )
        if native_name:
            row["native_ue_conceal_us"] = _value(
                native, "median_us", scheme=native_name, side="ue_conceal"
            )
            row["native_sidf_deconceal_us"] = _value(
                native, "median_us", scheme=native_name, side="sidf_deconceal"
            )
        if core_name and not e3.empty:
            s = e3[e3.scheme == core_name]
            row["nas_reg_request_bytes"] = s.nas_reg_request_bytes.median()
            row["e3_registration_median_ms"] = round(s.registration_ms.median(), 1)
            row["e3_registration_p95_ms"] = round(s.registration_ms.quantile(0.95), 1)
            row["e3_session_median_ms"] = round(s.session_ms.median(), 1)
        if core_name and not e4.empty:
            s = e4[e4.scheme == core_name]
            row["e4_100ue_registration_median_ms"] = round(s.registration_ms.median(), 1)
            row["e4_100ue_registration_p90_ms"] = round(s.registration_ms.quantile(0.9), 1)
        if core_name and not cpu.empty:
            s = cpu[cpu.scheme == core_name]
            row["e4_100ue_udm_cpu_ms_per_ue"] = round((_num(s.udm_cpu_s) * 1000 / 100).mean(), 2)
            row["e4_100ue_sessions_ok"] = " ".join(s.sessions_ok.astype(str))
        sid = scheme_ids.get(native_name or "")
        ok = interop[
            (interop.nas_scheme_id.astype(str) == sid) & (interop.match.astype(str) == "True")
        ]
        row["registered_on_core"] = "yes" if sid and not ok.empty else "not tested"
        rows.append(row)
    return rows


def main() -> None:
    """Write summary.csv and summary_notes.txt."""
    rows = summary_rows()
    fields = ["scheme", *NOTES]
    with (PROC / "summary.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, restval="")
        writer.writeheader()
        writer.writerows(rows)
    notes = "\n".join(f"{k}: {v}" for k, v in NOTES.items())
    (PROC / "summary_notes.txt").write_text("Column sources (results/processed/):\n" + notes + "\n")
    print(pd.read_csv(PROC / "summary.csv").to_string())


if __name__ == "__main__":
    main()
