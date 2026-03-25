#!/usr/bin/env python3
"""Export one nightly trend entry from dashboard/profile/gate artifacts."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _gate_state(row: Dict[str, Any]) -> str:
    if not row:
        return "UNKNOWN"
    if row.get("skipped") or row.get("observed") == "SKIPPED_C3_OFF":
        return "SKIPPED_C3_OFF"
    return "PASS" if bool(row.get("pass")) else "FAIL"


def _metric_dist(profile: Dict[str, Any], key: str) -> Dict[str, float]:
    node = (((profile.get("profile") or {}).get("distribution") or {}).get(key) or {})
    return {
        "p50": float(node.get("p50", 0.0) or 0.0),
        "p95": float(node.get("p95", 0.0) or 0.0),
    }


def _effects_status(effects: Dict[str, Any]) -> Dict[str, str]:
    # default conservative values
    status = {
        "open_loop": "UNKNOWN",
        "remove_self_state": "UNKNOWN",
        "disable_homeostasis": "UNKNOWN",
        "disable_broadcast": "UNKNOWN",
    }

    assertions = effects.get("structural_assertions") or []
    for row in assertions:
        name = str(row.get("name", "")).lower()
        st = "PASS" if bool(row.get("pass")) else "FAIL"
        if "open_loop" in name:
            status["open_loop"] = st
        elif "remove_self_state" in name:
            status["remove_self_state"] = st
        elif "disable_homeostasis" in name:
            status["disable_homeostasis"] = st
        elif "disable_broadcast" in name:
            status["disable_broadcast"] = st

    # if matrix has P1 result but no explicit assertion, mark available as PASS
    matrix = effects.get("effects") or {}
    if status["disable_broadcast"] == "UNKNOWN" and "P1" in matrix:
        status["disable_broadcast"] = "PASS"

    return status


def export_trend_entry(
    dashboard: Dict[str, Any],
    profile: Dict[str, Any],
    gate: Dict[str, Any],
    effects: Optional[Dict[str, Any]] = None,
    *,
    commit: str,
    date_utc: str,
) -> Dict[str, Any]:
    effects = effects or {}

    gate_rows = gate.get("gates") or []
    g1 = gate_rows[0] if len(gate_rows) > 0 else {}
    g2 = gate_rows[1] if len(gate_rows) > 1 else {}
    g3 = gate_rows[2] if len(gate_rows) > 2 else {}

    config = profile.get("config") or {}
    sentinel_selected = config.get("sentinel_scenarios_selected") or []

    out = {
        "date_utc": date_utc,
        "commit": commit,
        "sentinel": {
            "scenario": sentinel_selected[0] if sentinel_selected else "unknown",
            "rotation_mode": config.get("sentinel_rotation_mode", "unknown"),
        },
        "gate": {
            "overall": "PASS" if bool(gate.get("overall_pass")) else "FAIL",
            "gate1": _gate_state(g1),
            "gate2": _gate_state(g2),
            "gate3": _gate_state(g3),
        },
        "metrics": {
            "cycle_persistence_score": _metric_dist(profile, "cycle_persistence_score"),
            "dot_ratio": _metric_dist(profile, "dot_ratio"),
            "return_time_p95": float(_metric_dist(profile, "return_time_p95").get("p95", 0.0)),
            "order_invariance": {
                "score": _metric_dist(profile, "order_invariance_score"),
                "action_multiset": _metric_dist(profile, "order_invariance_action_multiset"),
                "goal_closure": _metric_dist(profile, "order_invariance_goal_closure"),
            },
            "sanity_ok_coverage": float(((profile.get("profile") or {}).get("sanity_ok_coverage", 0.0) or 0.0)),
        },
        "cycle_store": {
            "entries": int(((dashboard.get("cycle_store") or {}).get("entries", 0) or 0)),
            "evicted_entries": int(((dashboard.get("cycle_store") or {}).get("evicted_entries", 0) or 0)),
            "dedupe_rate": float(((dashboard.get("cycle_store") or {}).get("dedupe_rate", 0.0) or 0.0)),
        },
        "effects": _effects_status(effects),
        "threshold_recommendations": ((profile.get("profile") or {}).get("threshold_recommendations") or {}),
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dashboard", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--effects", default="")
    ap.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    ap.add_argument("--date-utc", default="")
    ap.add_argument("--out", default="artifacts/mvp11/trends/trend_entry.json")
    args = ap.parse_args()

    dashboard_path = Path(args.dashboard)
    profile_path = Path(args.profile)
    gate_path = Path(args.gate)
    effects_path = Path(args.effects) if args.effects else Path(str(profile_path).replace("profiles/nightly_soak_profile.json", "effects/nightly_cycle_effects.json"))

    dashboard = _load_json(dashboard_path)
    profile = _load_json(profile_path)
    gate = _load_json(gate_path)
    effects = _load_json(effects_path) if effects_path.exists() else {}

    date_utc = args.date_utc or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    commit = args.commit or "unknown"

    payload = export_trend_entry(dashboard, profile, gate, effects, commit=commit, date_utc=date_utc)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"output": str(out), "date_utc": payload["date_utc"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
