#!/usr/bin/env python3
"""Render MVP11 nightly cycle dashboard from profile/effects/gate artifacts."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def _pick_store_path(profile_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    # default beside artifacts root
    # .../artifacts/mvp11/profiles/nightly_soak_profile.json -> .../artifacts/mvp11/cycle_memory.json
    return profile_path.parent.parent / "cycle_memory.json"


def _gate_fail_reasons(gate: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    for row in gate.get("gates", []):
        if bool(row.get("pass")):
            continue
        reason = row.get("reason") or row.get("observed")
        reasons.append(f"{row.get('name')}: {reason}")
    return reasons


def _failed_assertions_top3(effects: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = effects.get("structural_assertions") or []
    out = []
    for row in rows:
        if bool(row.get("pass")):
            continue
        out.append(
            {
                "name": row.get("name"),
                "condition": row.get("condition"),
                "metric": row.get("metric"),
                "expected": row.get("expected"),
            }
        )
    return out[:3]


def _distribution_slice(profile: Dict[str, Any], key: str) -> Dict[str, Any]:
    dist = ((profile.get("profile") or {}).get("distribution") or {}).get(key) or {}
    return {
        "p50": dist.get("p50", 0.0),
        "p95": dist.get("p95", 0.0),
        "mean": dist.get("mean", 0.0),
    }


def _cycle_store_stats(store: Dict[str, Any]) -> Dict[str, Any]:
    if store.get("missing"):
        return {
            "present": False,
            "entries": 0,
            "evicted_entries": 0,
            "dedupe_rate": 0.0,
            "top_signatures": [],
        }

    items = store.get("items") or []
    entries = int(store.get("count", len(items)) or len(items))
    evicted = int(store.get("evicted_entries", 0) or 0)

    signatures = [str(i.get("signature", "")) for i in items if i.get("signature")]
    unique = len(set(signatures))
    dedupe_rate = round(1.0 - (unique / len(signatures)), 6) if signatures else 0.0

    # top signatures by counts
    ranked = sorted(
        items,
        key=lambda x: float((x.get("stats") or {}).get("counts", 0.0) or 0.0),
        reverse=True,
    )[:5]
    top = [
        {
            "signature": r.get("signature"),
            "counts": (r.get("stats") or {}).get("counts", 0),
        }
        for r in ranked
    ]

    return {
        "present": True,
        "entries": entries,
        "evicted_entries": evicted,
        "dedupe_rate": dedupe_rate,
        "top_signatures": top,
    }


def _render_md(payload: Dict[str, Any]) -> str:
    overall_icon = "✅" if payload.get("overall_pass") else "❌"
    g1 = payload.get("gate_1", {})
    g2 = payload.get("gate_2", {})
    g3 = payload.get("gate_3", {})

    lines = [
        "# MVP11 Nightly Cycle Dashboard",
        "",
        f"## Overall {overall_icon}",
        f"- overall_pass: `{payload.get('overall_pass')}`",
        f"- ts: `{payload.get('ts')}`",
        "",
        "## Gate-1 (Sanity Coverage)",
        f"- pass: `{g1.get('pass')}`",
        f"- sanity_ok_coverage: `{g1.get('sanity_ok_coverage')}`",
        f"- status_counts: `{g1.get('status_counts')}`",
        "",
        "## Gate-2 (Intervention Direction)",
        f"- pass: `{g2.get('pass')}`",
        f"- assertions: `{g2.get('passed_assertions')}/{g2.get('total_assertions')}`",
        "",
        "## Gate-3 (Main KPI, optional)",
        f"- pass: `{g3.get('pass')}`",
        f"- observed: `{g3.get('observed')}`",
        "",
        "## Distribution (p50/p95)",
        "",
    ]

    for k, v in payload.get("distribution", {}).items():
        lines.append(f"- {k}: p50=`{v.get('p50')}`, p95=`{v.get('p95')}`")

    oi = payload.get("order_invariance", {})
    lines.extend(
        [
            "",
            "## Order Invariance",
            f"- score: p50=`{(oi.get('score') or {}).get('p50')}`, p95=`{(oi.get('score') or {}).get('p95')}`",
            f"- action_multiset: p50=`{(oi.get('action_multiset') or {}).get('p50')}`, p95=`{(oi.get('action_multiset') or {}).get('p95')}`",
            f"- goal_closure: p50=`{(oi.get('goal_closure') or {}).get('p50')}`, p95=`{(oi.get('goal_closure') or {}).get('p95')}`",
            "",
            "## Cycle Store",
            f"- present: `{(payload.get('cycle_store') or {}).get('present')}`",
            f"- entries: `{(payload.get('cycle_store') or {}).get('entries')}`",
            f"- evicted_entries: `{(payload.get('cycle_store') or {}).get('evicted_entries')}`",
            f"- dedupe_rate: `{(payload.get('cycle_store') or {}).get('dedupe_rate')}`",
            "",
            "### Top signatures",
        ]
    )

    top = (payload.get("cycle_store") or {}).get("top_signatures") or []
    if not top:
        lines.append("- (none)")
    else:
        for row in top:
            lines.append(f"- `{row.get('signature')}` · counts={row.get('counts')}")

    fails = payload.get("failed_gate_reasons") or []
    if fails:
        lines.extend(["", "## Failed Gate Reasons"])
        lines.extend([f"- {r}" for r in fails])

    top3 = payload.get("failed_assertions_top3") or []
    if top3:
        lines.extend(["", "## Failed Assertions Top3"])
        for row in top3:
            lines.append(
                f"- {row.get('name')} ({row.get('condition')} · {row.get('metric')}) expected `{row.get('expected')}`"
            )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--effects", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--cycle-store", default="")
    ap.add_argument("--out-md", default="artifacts/mvp11/dashboard/nightly_dashboard.md")
    ap.add_argument("--out-json", default="artifacts/mvp11/dashboard/nightly_dashboard.json")
    args = ap.parse_args()

    profile_path = Path(args.profile)
    effects_path = Path(args.effects)
    gate_path = Path(args.gate)
    store_path = _pick_store_path(profile_path, args.cycle_store)

    profile = _load_json(profile_path)
    effects = _load_json(effects_path)
    gate = _load_json(gate_path)
    store = _load_json(store_path)

    gate_rows = gate.get("gates") or []
    gate_1 = gate_rows[0] if len(gate_rows) > 0 else {}
    gate_2 = gate_rows[1] if len(gate_rows) > 1 else {}
    gate_3 = gate_rows[2] if len(gate_rows) > 2 else {}

    assertions = effects.get("structural_assertions") or []
    pass_count = sum(1 for r in assertions if bool(r.get("pass")))

    payload = {
        "schema_version": "mvp11.cycle_dashboard.v1",
        "ts": time.time(),
        "overall_pass": bool(gate.get("overall_pass", False)),
        "gate_1": {
            "pass": gate_1.get("pass"),
            "sanity_ok_coverage": gate_1.get("observed"),
            "status_counts": gate_1.get("status_counts", {}),
        },
        "gate_2": {
            "pass": gate_2.get("pass"),
            "passed_assertions": pass_count,
            "total_assertions": len(assertions),
        },
        "gate_3": {
            "pass": gate_3.get("pass"),
            "observed": gate_3.get("observed"),
        },
        "distribution": {
            "cycle_persistence_score": _distribution_slice(profile, "cycle_persistence_score"),
            "dot_ratio": _distribution_slice(profile, "dot_ratio"),
            "return_time_p95": _distribution_slice(profile, "return_time_p95"),
            "governor_block_rate": _distribution_slice(profile, "governor_block_rate"),
            "homeostasis_drift_mean": _distribution_slice(profile, "homeostasis_drift_mean"),
        },
        "order_invariance": {
            "score": _distribution_slice(profile, "order_invariance_score"),
            "action_multiset": _distribution_slice(profile, "order_invariance_action_multiset"),
            "goal_closure": _distribution_slice(profile, "order_invariance_goal_closure"),
        },
        "cycle_store": _cycle_store_stats(store),
        "failed_gate_reasons": _gate_fail_reasons(gate),
        "failed_assertions_top3": _failed_assertions_top3(effects),
        "inputs": {
            "profile": str(profile_path),
            "effects": str(effects_path),
            "gate": str(gate_path),
            "cycle_store": str(store_path),
        },
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_render_md(payload), encoding="utf-8")

    print(json.dumps({"output_json": str(out_json), "output_md": str(out_md), "overall_pass": payload["overall_pass"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
