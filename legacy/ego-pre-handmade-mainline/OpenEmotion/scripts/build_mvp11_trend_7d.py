#!/usr/bin/env python3
"""Build 7-day trend summary (json + markdown) from trend entries.

MVP11.3.3: Adds scenario-stratified trend analysis (baseline/focused/wide).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SPARKS = "▁▂▃▄▅▆▇█"
SCENARIOS = ["baseline", "focused", "wide"]
K_RECENT = 5  # Number of recent observations per scenario


# Concentration thresholds (Light mode - WARN only, no fail)
CONCENTRATION_WARN_TOP1 = 0.55  # > 0.55 -> potential single-cycle collapse
CONCENTRATION_WARN_HHI = 0.25  # > 0.25 -> high concentration


def _load_entries(entries_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in sorted(entries_dir.rglob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "date_utc" not in data:
            continue
        data["_source"] = str(p)
        rows.append(data)

    rows.sort(key=lambda x: (x.get("date_utc", ""), x.get("commit", ""), x.get("_source", "")))
    return rows


def _tail(entries: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    if n <= 0:
        return entries
    return entries[-n:]


def _series(entries: List[Dict[str, Any]], getter) -> List[float]:
    out: List[float] = []
    for e in entries:
        try:
            out.append(float(getter(e)))
        except Exception:
            out.append(0.0)
    return out


def _sparkline(values: List[Optional[float]], *, higher_better: bool = True) -> str:
    """Generate sparkline from values, supporting None for missing data."""
    if not values:
        return ""
    
    # Filter out None values for normalization
    valid_vals = [v for v in values if v is not None]
    if not valid_vals:
        return "·" * len(values)
    
    # Normalize valid values
    vmin = min(valid_vals)
    vmax = max(valid_vals)
    
    out = []
    for v in values:
        if v is None:
            out.append("·")  # Missing data placeholder
        elif math.isclose(vmin, vmax):
            out.append(SPARKS[0])
        else:
            norm = (v - vmin) / (vmax - vmin)
            if not higher_better:
                norm = 1.0 - norm
            idx = int(round(norm * (len(SPARKS) - 1)))
            idx = max(0, min(len(SPARKS) - 1, idx))
            out.append(SPARKS[idx])
    return "".join(out)


def _slope(values: List[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return num / den


def _drift_score(entry: Dict[str, Any]) -> float:
    m = entry.get("metrics") or {}
    t = entry.get("threshold_recommendations") or {}

    score = 0.0

    sanity = float(m.get("sanity_ok_coverage", 0.0) or 0.0)
    sanity_min = float(t.get("sanity_ok_rate_min", 0.99) or 0.99)
    if sanity < sanity_min:
        score += (sanity_min - sanity) / max(1e-6, sanity_min)

    pers = (m.get("cycle_persistence_score") or {})
    pers_p95 = float(pers.get("p95", 0.0) or 0.0)
    pers_range = t.get("cycle_persistence_score_range") or {}
    pmin = float(pers_range.get("min", 0.0) or 0.0)
    pmax = float(pers_range.get("max", 1.0) or 1.0)
    if pers_p95 < pmin:
        score += (pmin - pers_p95) / max(1e-6, abs(pmax - pmin) or 1.0)
    elif pers_p95 > pmax:
        score += (pers_p95 - pmax) / max(1e-6, abs(pmax - pmin) or 1.0)

    dot = (m.get("dot_ratio") or {})
    dot_p95 = float(dot.get("p95", 0.0) or 0.0)
    dot_range = t.get("dot_ratio_range") or {}
    dot_max = float(dot_range.get("max", 1.0) or 1.0)
    if dot_p95 > dot_max:
        score += (dot_p95 - dot_max) / max(1e-6, dot_max)

    rt_p95 = float(m.get("return_time_p95", 0.0) or 0.0)
    rt_max = float(t.get("return_time_p95_max", 0.0) or 0.0)
    if rt_max > 0 and rt_p95 > rt_max:
        score += (rt_p95 - rt_max) / max(1e-6, rt_max)

    return round(score, 6)


def _symbol(state: str) -> str:
    mapping = {
        "PASS": "✅",
        "FAIL": "⚠️",
        "SKIPPED_C3_OFF": "⏭️",
    }
    return mapping.get(state, "❔")


def _get_scenario(entry: Dict[str, Any]) -> str:
    """Extract scenario from entry, default to 'unknown'."""
    sentinel = entry.get("sentinel") or {}
    scenario = sentinel.get("scenario", "unknown")
    # Handle case where scenario might be a list
    if isinstance(scenario, list):
        scenario = scenario[0] if scenario else "unknown"
    return str(scenario)


def _extract_phi_signature(entry: Dict[str, Any]) -> Optional[str]:
    """Extract phi signature from entry for concentration calculation.
    
    Looks for:
    1. cycle_signature field
    2. phi hash from cycle_store
    3. signature field
    """
    # Try cycle_signature first
    sig = entry.get("cycle_signature")
    if sig:
        return str(sig)
    
    # Try signature field
    sig = entry.get("signature")
    if sig:
        return str(sig)
    
    # Try phi dict -> hash it
    phi = entry.get("phi") or (entry.get("prototype_bucket") or {}).get("phi")
    if phi and isinstance(phi, dict):
        # Create a deterministic string from phi dict
        phi_str = json.dumps(phi, sort_keys=True)
        return phi_str
    
    return None


def compute_concentration(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute signature concentration metrics from trend entries.
    
    MVP11.4.5: Adds concentration fields for chronic degradation detection.
    
    Returns:
        - phi_top1_share: top-1 signature share (0.0-1.0)
        - phi_top3_share: top-3 signatures share (0.0-1.0)
        - phi_hhi: Herfindahl-Hirschman Index (0.0-1.0)
        - unique_phi_per_1000: unique signatures per 1000 observations
        - warnings: list of threshold violations (Light mode)
    """
    result = {
        "phi_top1_share": None,
        "phi_top3_share": None,
        "phi_hhi": None,
        "unique_phi_per_1000": None,
        "warnings": [],
    }
    
    # Extract signatures from entries
    signatures = []
    for entry in entries:
        sig = _extract_phi_signature(entry)
        if sig:
            signatures.append(sig)
    
    if not signatures:
        return result
    
    # Compute concentration metrics
    counts = Counter(signatures)
    total = len(signatures)
    sorted_counts = sorted(counts.values(), reverse=True)
    
    # Top-1 share
    top1_share = sorted_counts[0] / total if sorted_counts else 0.0
    
    # Top-3 share
    top3_share = sum(sorted_counts[:3]) / total if sorted_counts else 0.0
    
    # HHI (Herfindahl-Hirschman Index)
    hhi = sum((c / total) ** 2 for c in counts.values())
    
    # Unique per 1000
    unique_per_1000 = (len(counts) / total) * 1000 if total > 0 else 0.0
    
    result["phi_top1_share"] = round(top1_share, 6)
    result["phi_top3_share"] = round(top3_share, 6)
    result["phi_hhi"] = round(hhi, 6)
    result["unique_phi_per_1000"] = round(unique_per_1000, 2)
    
    # Light mode warnings (do not fail, just warn)
    if top1_share > CONCENTRATION_WARN_TOP1:
        result["warnings"].append(
            f"phi_top1_share={top1_share:.3f} > {CONCENTRATION_WARN_TOP1} (potential single-cycle collapse)"
        )
    
    if hhi > CONCENTRATION_WARN_HHI:
        result["warnings"].append(
            f"phi_hhi={hhi:.3f} > {CONCENTRATION_WARN_HHI} (high concentration)"
        )
    
    return result


def _get_dates_window(entries: List[Dict[str, Any]], window_days: int) -> List[str]:
    """Get list of date strings for the window, filling gaps."""
    if not entries:
        return []
    
    # Get date range from entries
    dates = sorted(set(e.get("date_utc", "") for e in entries if e.get("date_utc")))
    if not dates:
        return []
    
    # Parse first and last dates
    try:
        start = datetime.strptime(dates[0], "%Y-%m-%d")
        end = datetime.strptime(dates[-1], "%Y-%m-%d")
    except ValueError:
        return dates
    
    # Generate all dates in range
    all_dates = []
    current = start
    while current <= end:
        all_dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    return all_dates[-window_days:] if len(all_dates) > window_days else all_dates


def build_scenario_series(
    entries: List[Dict[str, Any]],
    dates: List[str],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int], Dict[str, List[Dict[str, Any]]]]:
    """Build scenario-stratified series data.
    
    Returns:
        - scenario_series: metrics per scenario keyed by date
        - scenario_counts: sample count per scenario
        - recent_observations: K most recent entries per scenario (beyond window)
    """
    # Group entries by scenario and date
    by_scenario_date: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    for e in entries:
        scenario = _get_scenario(e)
        date = e.get("date_utc", "")
        by_scenario_date[scenario][date].append(e)
        by_scenario[scenario].append(e)
    
    # Build scenario series
    scenario_series: Dict[str, Dict[str, Any]] = {}
    
    for scenario in SCENARIOS:
        scenario_entries = by_scenario_date.get(scenario, {})
        
        # Build metrics series with nulls for missing dates
        persistence_p50: List[Optional[float]] = []
        persistence_p95: List[Optional[float]] = []
        dot_ratio_p50: List[Optional[float]] = []
        dot_ratio_p95: List[Optional[float]] = []
        sanity_coverage: List[Optional[float]] = []
        gates: List[Dict[str, str]] = []
        
        for date in dates:
            day_entries = scenario_entries.get(date, [])
            if not day_entries:
                persistence_p50.append(None)
                persistence_p95.append(None)
                dot_ratio_p50.append(None)
                dot_ratio_p95.append(None)
                sanity_coverage.append(None)
                gates.append({})
            else:
                # Aggregate metrics for the day (take first entry if multiple)
                e = day_entries[0]
                m = e.get("metrics") or {}
                
                cps = m.get("cycle_persistence_score") or {}
                persistence_p50.append(float(cps.get("p50", 0.0) or 0.0))
                persistence_p95.append(float(cps.get("p95", 0.0) or 0.0))
                
                dr = m.get("dot_ratio") or {}
                dot_ratio_p50.append(float(dr.get("p50", 0.0) or 0.0))
                dot_ratio_p95.append(float(dr.get("p95", 0.0) or 0.0))
                
                sanity_coverage.append(float(m.get("sanity_ok_coverage", 0.0) or 0.0))
                
                g = e.get("gate") or {}
                gates.append({
                    "gate1": g.get("gate1", "UNKNOWN"),
                    "gate2": g.get("gate2", "UNKNOWN"),
                    "gate3": g.get("gate3", "UNKNOWN"),
                    "overall": g.get("overall", "UNKNOWN"),
                })
        
        scenario_series[scenario] = {
            "persistence_p50": persistence_p50,
            "persistence_p95": persistence_p95,
            "dot_ratio_p50": dot_ratio_p50,
            "dot_ratio_p95": dot_ratio_p95,
            "sanity_ok_coverage": sanity_coverage,
            "gates": gates,
            "sparklines": {
                "persistence_p50": _sparkline(persistence_p50, higher_better=True),
                "dot_ratio_p50": _sparkline(dot_ratio_p50, higher_better=False),
                "sanity_ok_coverage": _sparkline(sanity_coverage, higher_better=True),
            },
        }
    
    # Build scenario counts
    scenario_counts: Dict[str, int] = {}
    for scenario in SCENARIOS:
        scenario_counts[scenario] = len(by_scenario.get(scenario, []))
    
    # Build recent observations (K most recent per scenario, beyond the window)
    recent_observations: Dict[str, List[Dict[str, Any]]] = {}
    for scenario in SCENARIOS:
        all_scenario_entries = sorted(
            by_scenario.get(scenario, []),
            key=lambda x: x.get("date_utc", ""),
            reverse=True
        )
        recent_observations[scenario] = all_scenario_entries[:K_RECENT]
    
    return scenario_series, scenario_counts, recent_observations


def build_trend(entries: List[Dict[str, Any]], *, alert_threshold: float, window_days: int = 7) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for e in entries:
        row = dict(e)
        row["drift_score"] = _drift_score(e)
        rows.append(row)

    p50_persistence = _series(rows, lambda x: ((x.get("metrics") or {}).get("cycle_persistence_score") or {}).get("p50", 0.0))
    p50_dot = _series(rows, lambda x: ((x.get("metrics") or {}).get("dot_ratio") or {}).get("p50", 0.0))
    sanity_cov = _series(rows, lambda x: (x.get("metrics") or {}).get("sanity_ok_coverage", 0.0))

    latest = rows[-1] if rows else {}
    latest_drift = float(latest.get("drift_score", 0.0) or 0.0)

    # Build dates window for scenario series
    dates = _get_dates_window(rows, window_days)
    
    # Build scenario-stratified data
    scenario_series, scenario_counts, recent_observations = build_scenario_series(rows, dates)

    # Compute concentration metrics (MVP11.4.5)
    concentration = compute_concentration(rows)

    payload = {
        "schema_version": "mvp11.cycle_trend_7d.v1",
        "ts": time.time(),
        "window_days": len(rows),
        "dates": dates,
        "entries": rows,
        "sparklines": {
            "cycle_persistence_p50": _sparkline(p50_persistence, higher_better=True),
            "dot_ratio_p50": _sparkline(p50_dot, higher_better=False),
            "sanity_ok_coverage": _sparkline(sanity_cov, higher_better=True),
        },
        "slopes": {
            "cycle_persistence_p50": round(_slope(p50_persistence), 6),
            "dot_ratio_p50": round(_slope(p50_dot), 6),
            "sanity_ok_coverage": round(_slope(sanity_cov), 6),
        },
        "drift": {
            "latest_score": round(latest_drift, 6),
            "alert_threshold": float(alert_threshold),
            "potential_drift": bool(latest_drift > alert_threshold),
        },
        "concentration": concentration,
        "scenario_series": scenario_series,
        "scenario_counts": scenario_counts,
        "recent_observations": recent_observations,
    }
    return payload


def render_markdown(trend: Dict[str, Any]) -> str:
    rows = trend.get("entries") or []
    dates = trend.get("dates") or []
    scenario_series = trend.get("scenario_series") or {}
    scenario_counts = trend.get("scenario_counts") or {}
    recent_observations = trend.get("recent_observations") or {}

    lines = [
        "## 7-Day Trend",
        "",
        "Date | G1 | G2 | G3 | Overall | Sentinel | Drift",
        "--- | --- | --- | --- | --- | --- | ---",
    ]

    for e in rows:
        d = e.get("date_utc", "")
        try:
            d2 = datetime.strptime(d, "%Y-%m-%d").strftime("%m-%d")
        except Exception:
            d2 = d
        g = e.get("gate") or {}
        sentinel = ((e.get("sentinel") or {}).get("scenario") or "unknown")
        if isinstance(sentinel, list):
            sentinel = sentinel[0] if sentinel else "unknown"
        drift = float(e.get("drift_score", 0.0) or 0.0)
        lines.append(
            f"{d2} | {_symbol(g.get('gate1','UNKNOWN'))} | {_symbol(g.get('gate2','UNKNOWN'))} | {_symbol(g.get('gate3','UNKNOWN'))} | {_symbol(g.get('overall','UNKNOWN'))} | {sentinel} | {drift:.3f}"
        )

    lines.extend(
        [
            "",
            "### Sparklines",
            f"- cycle_persistence_p50 (higher better): `{(trend.get('sparklines') or {}).get('cycle_persistence_p50','')}`",
            f"- dot_ratio_p50 (lower better): `{(trend.get('sparklines') or {}).get('dot_ratio_p50','')}`",
            f"- sanity_ok_coverage: `{(trend.get('sparklines') or {}).get('sanity_ok_coverage','')}`",
            "",
            f"### Drift Alert\n- latest drift_score: `{(trend.get('drift') or {}).get('latest_score',0.0)}`",
        ]
    )

    if (trend.get("drift") or {}).get("potential_drift"):
        lines.append("- ⚠️ potential drift")
    else:
        lines.append("- ✅ no significant drift")
    
    # Scenario Trend Panel
    lines.extend(
        [
            "",
            "### Scenario Trend Panel",
            "",
        ]
    )
    
    # Gate heatmap by scenario
    lines.append("#### Gate Heatmap by Scenario")
    lines.append("")
    lines.append("Scenario | " + " | ".join(d[-5:] for d in dates) + " | n | last")
    lines.append("--- | " + " | ".join(["---"] * len(dates)) + " | --- | ---")
    
    for scenario in SCENARIOS:
        series = scenario_series.get(scenario, {})
        gates = series.get("gates", [])
        
        # Build gate symbols for each date
        gate_symbols = []
        for i, date in enumerate(dates):
            if i < len(gates):
                g = gates[i]
                overall = g.get("overall", "")
                if overall == "PASS":
                    gate_symbols.append("✅")
                elif overall == "FAIL":
                    gate_symbols.append("⚠️")
                elif overall == "SKIPPED_C3_OFF":
                    gate_symbols.append("⏭️")
                elif not g:  # Missing data
                    gate_symbols.append("·")
                else:
                    gate_symbols.append("❔")
            else:
                gate_symbols.append("·")
        
        # Count and last-seen
        count = scenario_counts.get(scenario, 0)
        recent = recent_observations.get(scenario, [])
        last_date = recent[0].get("date_utc", "-") if recent else "-"
        if last_date and last_date != "-":
            try:
                last_date = datetime.strptime(last_date, "%Y-%m-%d").strftime("%m-%d")
            except ValueError:
                pass
        
        lines.append(f"{scenario} | " + " | ".join(gate_symbols) + f" | {count} | {last_date}")
    
    # Per-scenario sparklines
    lines.extend(
        [
            "",
            "#### Per-Scenario Sparklines",
            "",
        ]
    )
    
    for scenario in SCENARIOS:
        series = scenario_series.get(scenario, {})
        sparks = series.get("sparklines", {})
        count = scenario_counts.get(scenario, 0)
        
        pers_spark = sparks.get("persistence_p50", "")
        dot_spark = sparks.get("dot_ratio_p50", "")
        sanity_spark = sparks.get("sanity_ok_coverage", "")
        
        lines.append(f"**{scenario}** (n={count})")
        lines.append(f"- persistence_p50: `{pers_spark or '·'}`")
        lines.append(f"- dot_ratio_p50: `{dot_spark or '·'}`")
        lines.append(f"- sanity_ok_coverage: `{sanity_spark or '·'}`")
        lines.append("")
    
    # Recent K=5 observations per scenario
    lines.extend(
        [
            "#### Recent K=5 Observations",
            "",
        ]
    )
    
    for scenario in SCENARIOS:
        recent = recent_observations.get(scenario, [])
        lines.append(f"**{scenario}**")
        
        if not recent:
            lines.append("- no observations")
        else:
            for obs in recent:
                date = obs.get("date_utc", "?")
                g = obs.get("gate") or {}
                overall = g.get("overall", "?")
                m = obs.get("metrics") or {}
                cps = (m.get("cycle_persistence_score") or {}).get("p50", "?")
                dot = (m.get("dot_ratio") or {}).get("p50", "?")
                lines.append(f"- {date}: overall={_symbol(overall)} persistence_p50={cps} dot_ratio_p50={dot}")
        
        lines.append("")
    
    # Concentration section (MVP11.4.5)
    concentration = trend.get("concentration") or {}
    if concentration.get("phi_top1_share") is not None:
        lines.extend(
            [
                "### Signature Concentration",
                "",
                f"- **Top1 Share**: `{concentration.get('phi_top1_share', 'N/A')}`",
                f"- **Top3 Share**: `{concentration.get('phi_top3_share', 'N/A')}`",
                f"- **HHI**: `{concentration.get('phi_hhi', 'N/A')}`",
                f"- **Unique/1000**: `{concentration.get('unique_phi_per_1000', 'N/A')}`",
            ]
        )
        
        # Show warnings if any
        warnings = concentration.get("warnings", [])
        if warnings:
            lines.extend(["", "#### ⚠️ Concentration Warnings", ""])
            for w in warnings:
                lines.append(f"- {w}")
        
        lines.append("")
    
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entries-dir", required=True)
    ap.add_argument("--out-json", default="artifacts/mvp11/trends/trend_7d.json")
    ap.add_argument("--out-md", default="artifacts/mvp11/trends/trend_7d.md")
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--drift-alert-threshold", type=float, default=0.2)
    args = ap.parse_args()

    entries = _load_entries(Path(args.entries_dir))
    entries = _tail(entries, args.window)

    trend = build_trend(entries, alert_threshold=args.drift_alert_threshold, window_days=args.window)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(trend, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(trend), encoding="utf-8")

    print(json.dumps({"output_json": str(out_json), "output_md": str(out_md), "window_days": trend.get("window_days", 0)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
