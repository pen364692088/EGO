"""Cycle observability + analysis helpers for MVP11.2.

This module keeps cycle logic deterministic and lightweight so it can run in CI.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from statistics import mean, median
from typing import Any, Dict, List, Set, Tuple


SANITY_EPS_DEFAULT = 1e-6


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def quantize(value: Any, step: float = 0.2) -> float:
    """Quantize numeric values to reduce tiny floating drift in signatures."""
    if step <= 0:
        raise ValueError("step must be > 0")
    v = _safe_float(value, 0.0)
    q = round(v / step) * step
    # keep stable text/JSON representation
    return round(q, 6)


def _focus_cluster(focus: Any) -> str:
    if focus is None:
        return "none"
    txt = str(focus)
    # Stable low-cardinality grouping prevents every goal id becoming its own state.
    digest = hashlib.sha1(txt.encode("utf-8")).hexdigest()
    return f"f{int(digest[:2], 16) % 8}"


def _pick_hs(hs: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in hs:
            return _safe_float(hs.get(k), default)
    return default


def _canonical_signature_payload(bucket: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical payload for backward-compatible cycle signature.

    Important: this intentionally ignores extension fields (e.g. psi/phi/schema_version)
    so signature stability is preserved across bucket schema evolution.
    """
    if not isinstance(bucket, dict):
        return {
            "scenario_id": "global",
            "focus": "none",
            "intent": "none",
            "action_type": None,
            "gov": None,
            "intervention": None,
            "hs": {"energy": 0.0, "safety": 0.0, "certainty": 0.0, "autonomy": 0.0},
            "efe": {"risk": 0.0, "ambiguity": 0.0, "info_gain": 0.0, "cost": 0.0},
        }

    psi = bucket.get("psi") or {}
    phi = bucket.get("phi") or {}
    hs = bucket.get("hs") or phi.get("hs") or {}
    efe = bucket.get("efe") or phi.get("efe") or {}

    return {
        "scenario_id": bucket.get("scenario_id", psi.get("scenario_id", "global")),
        "focus": bucket.get("focus", psi.get("focus", "none")),
        "intent": bucket.get("intent", psi.get("intent", "none")),
        "action_type": bucket.get("action_type", psi.get("action_type")),
        "gov": bucket.get("gov", psi.get("gov")),
        "intervention": bucket.get("intervention", psi.get("intervention")),
        "hs": {
            "energy": quantize((hs or {}).get("energy", 0.0)),
            "safety": quantize((hs or {}).get("safety", 0.0)),
            "certainty": quantize((hs or {}).get("certainty", 0.0)),
            "autonomy": quantize((hs or {}).get("autonomy", 0.0)),
        },
        "efe": {
            "risk": quantize((efe or {}).get("risk", 0.0)),
            "ambiguity": quantize((efe or {}).get("ambiguity", 0.0)),
            "info_gain": quantize((efe or {}).get("info_gain", 0.0)),
            "cost": quantize((efe or {}).get("cost", 0.0)),
        },
    }


def _extract_psi(bucket: Dict[str, Any]) -> Dict[str, Any]:
    c = _canonical_signature_payload(bucket)
    return {
        "scenario_id": c["scenario_id"],
        "focus": c["focus"],
        "intent": c["intent"],
        "action_type": c["action_type"],
        "gov": c["gov"],
        "intervention": c["intervention"],
    }


def _extract_phi(bucket: Dict[str, Any]) -> Dict[str, Any]:
    c = _canonical_signature_payload(bucket)
    phi = {
        "hs": c["hs"],
        "efe": c["efe"],
    }
    # optional, low-cardinality adjunct if already present
    raw_phi = (bucket or {}).get("phi") or {}
    if "self_state_cluster" in raw_phi:
        phi["self_state_cluster"] = str(raw_phi.get("self_state_cluster"))
    return phi


def build_cycle_bucket(event: Dict[str, Any]) -> Dict[str, Any]:
    """Build deterministic bucket from causal-core fields only.

    Excludes volatile fields (ts/run_id/tick/raw text).
    """
    hs = event.get("homeostasis_state") or {}
    efe = event.get("efe_terms") or event.get("efe") or {}
    gov = event.get("governor_decision") or event.get("governor") or {}
    action = event.get("action") or {}

    base = {
        "scenario_id": event.get("scenario_id") or event.get("goal_id") or "global",
        "focus": _focus_cluster(event.get("chosen_focus")),
        "intent": event.get("chosen_intent") or "none",
        "action_type": action.get("type"),
        "gov": gov.get("decision") or gov.get("action"),
        "intervention": event.get("intervention"),
        "hs": {
            "energy": quantize(_pick_hs(hs, "energy", "energy_budget")),
            "safety": quantize(_pick_hs(hs, "safety", "risk_exposure")),
            "certainty": quantize(_pick_hs(hs, "certainty", "uncertainty")),
            "autonomy": quantize(_pick_hs(hs, "autonomy", "compute_pressure")),
        },
        "efe": {
            "risk": quantize(efe.get("risk", 0.0)),
            "ambiguity": quantize(efe.get("ambiguity", 0.0)),
            "info_gain": quantize(efe.get("info_gain", 0.0)),
            "cost": quantize(efe.get("cost", efe.get("expected_cost", 0.0))),
        },
    }

    psi = {
        "scenario_id": base["scenario_id"],
        "focus": base["focus"],
        "intent": base["intent"],
        "action_type": base["action_type"],
        "gov": base["gov"],
        "intervention": base["intervention"],
    }

    phi = {
        "hs": dict(base["hs"]),
        "efe": dict(base["efe"]),
    }

    # optional low-cardinality content adjunct; excluded from canonical signature
    self_state = event.get("self_state") or {}
    if isinstance(self_state, dict) and self_state:
        marker = json.dumps(sorted(self_state.keys()), ensure_ascii=False)
        phi["self_state_cluster"] = _focus_cluster(marker)

    bucket = {
        **base,
        "psi": psi,
        "phi": phi,
        "bucket_schema_version": "mvp11.4.v1",
    }
    return bucket

def signature(bucket: Dict[str, Any], size: int = 16) -> str:
    payload = json.dumps(
        _canonical_signature_payload(bucket),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:size]


def signature_psi(bucket: Dict[str, Any], size: int = 16) -> str:
    payload = json.dumps(_extract_psi(bucket), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:size]


def signature_phi(bucket: Dict[str, Any], size: int = 16) -> str:
    payload = json.dumps(_extract_phi(bucket), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:size]


def annotate_event_with_cycle(event: Dict[str, Any]) -> Dict[str, Any]:
    """Attach cycle_bucket + cycle signatures to an event in-place."""
    bucket = build_cycle_bucket(event)
    event["cycle_bucket"] = bucket
    event["cycle_signature"] = signature(bucket)
    event["cycle_signature_psi"] = signature_psi(bucket)
    event["cycle_signature_phi"] = signature_phi(bucket)
    return event


def _scc_kosaraju(nodes: List[str], edges: Dict[str, List[str]]) -> List[List[str]]:
    visited: set[str] = set()
    order: List[str] = []

    def dfs(u: str) -> None:
        visited.add(u)
        for v in edges.get(u, []):
            if v not in visited:
                dfs(v)
        order.append(u)

    for n in nodes:
        if n not in visited:
            dfs(n)

    redges: Dict[str, List[str]] = defaultdict(list)
    for u, vs in edges.items():
        for v in vs:
            redges[v].append(u)

    comps: List[List[str]] = []
    visited2: set[str] = set()

    def rdfs(u: str, comp: List[str]) -> None:
        visited2.add(u)
        comp.append(u)
        for v in redges.get(u, []):
            if v not in visited2:
                rdfs(v, comp)

    for n in reversed(order):
        if n not in visited2:
            comp: List[str] = []
            rdfs(n, comp)
            comps.append(comp)

    return comps


def _multiset_jaccard(a: Counter[str], b: Counter[str]) -> float:
    keys = set(a.keys()) | set(b.keys())
    if not keys:
        return 1.0
    inter = sum(min(a.get(k, 0), b.get(k, 0)) for k in keys)
    union = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return inter / union if union > 0 else 1.0


def _window_action_multiset(events: List[Dict[str, Any]], start: int, end: int) -> Counter[str]:
    window = events[start : end + 1]
    return Counter((e.get("action") or {}).get("type", "unknown") for e in window)


def _window_goal_closure_signature(events: List[Dict[str, Any]], start: int, end: int) -> str:
    """Closure descriptor for a cycle window.

    Uses endpoint semantic fields to distinguish
    "action sequence changed" vs "goal closure changed".
    """
    end_event = events[end]
    action = end_event.get("action") or {}
    outcome = end_event.get("outcome") or {}

    payload = {
        "focus": end_event.get("chosen_focus") or "none",
        "intent": end_event.get("chosen_intent") or "none",
        "action_type": action.get("type") or "unknown",
        "outcome_status": outcome.get("status") or "unknown",
    }
    txt = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(txt.encode("utf-8")).hexdigest()[:12]


def _compute_order_invariance_decomposed(events: List[Dict[str, Any]], signatures: List[str]) -> Tuple[float, float, float]:
    # Build cycle windows for each repeating signature.
    positions: Dict[str, List[int]] = defaultdict(list)
    for idx, sig in enumerate(signatures):
        positions[sig].append(idx)

    window_multisets: List[Counter[str]] = []
    window_closures: List[str] = []
    for _sig, idxs in positions.items():
        if len(idxs) < 3:
            continue
        for a, b in zip(idxs, idxs[1:]):
            if b <= a:
                continue
            window_multisets.append(_window_action_multiset(events, a, b))
            window_closures.append(_window_goal_closure_signature(events, a, b))

    if len(window_multisets) < 2:
        return 0.0, 0.0, 0.0

    action_sims = [_multiset_jaccard(x, y) for x, y in combinations(window_multisets, 2)]
    action_score = round(sum(action_sims) / len(action_sims), 6) if action_sims else 0.0

    closure_pairs = list(combinations(window_closures, 2))
    if closure_pairs:
        closure_same = sum(1 for a, b in closure_pairs if a == b)
        closure_score = round(closure_same / len(closure_pairs), 6)
    else:
        closure_score = 0.0

    combined = round((action_score + closure_score) / 2.0, 6)
    return action_score, closure_score, combined


def _compute_order_invariance(events: List[Dict[str, Any]], signatures: List[str]) -> float:
    _action, _closure, score = _compute_order_invariance_decomposed(events, signatures)
    return score


def _signature_order_invariance(events: List[Dict[str, Any]], idxs: List[int]) -> float:
    """Order invariance for one signature via pairwise window multiset similarity."""
    if len(idxs) < 3:
        return 0.0

    windows: List[Counter[str]] = []
    for a, b in zip(idxs, idxs[1:]):
        if b <= a:
            continue
        windows.append(_window_action_multiset(events, a, b))

    if len(windows) < 2:
        return 0.0

    sims = [_multiset_jaccard(x, y) for x, y in combinations(windows, 2)]
    return round(sum(sims) / len(sims), 6) if sims else 0.0


def _dominant_transitions(signatures: List[str], topk: int = 5) -> List[Dict[str, Any]]:
    if len(signatures) < 2:
        return []
    pairs = Counter((a, b) for a, b in zip(signatures, signatures[1:]))
    result: List[Dict[str, Any]] = []
    for (a, b), c in pairs.most_common(topk):
        result.append({"from": a, "to": b, "count": c})
    return result


def _return_times(signatures: List[str]) -> List[int]:
    last: Dict[str, int] = {}
    gaps: List[int] = []
    for idx, sig in enumerate(signatures):
        if sig in last:
            gaps.append(idx - last[sig])
        last[sig] = idx
    return gaps


def _obstruction_count(signatures: List[str]) -> int:
    """Approximate overlap obstruction: same source branching to many successors."""
    nexts: Dict[str, set[str]] = defaultdict(set)
    for a, b in zip(signatures, signatures[1:]):
        nexts[a].add(b)
    return sum(1 for _, outs in nexts.items() if len(outs) >= 3)


def extract_signatures(events: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for event in events:
        sig = event.get("cycle_signature")
        if not sig:
            sig = signature(build_cycle_bucket(event))
        out.append(str(sig))
    return out


def _build_graph(signatures: List[str]) -> Tuple[List[str], Dict[str, List[str]], Dict[str, Set[str]], Counter[str]]:
    nodes = list(dict.fromkeys(signatures))
    edges: Dict[str, List[str]] = defaultdict(list)
    edge_sets: Dict[str, Set[str]] = defaultdict(set)
    for a, b in zip(signatures, signatures[1:]):
        edges[a].append(b)
        edge_sets[a].add(b)
    counts = Counter(signatures)
    return nodes, edges, edge_sets, counts


def _compute_scc_nodes(nodes: List[str], edges: Dict[str, List[str]], counts: Counter[str]) -> Set[str]:
    comps = _scc_kosaraju(nodes, edges)
    scc_nodes: Set[str] = set()
    for comp in comps:
        if len(comp) >= 2:
            scc_nodes.update(comp)
        elif len(comp) == 1:
            u = comp[0]
            if u in edges.get(u, []):
                scc_nodes.add(u)

    # C0.1 hard guard: one-off nodes (dots) cannot be cycle members.
    return {s for s in scc_nodes if counts.get(s, 0) >= 2}


def compute_cycle_sanity(dot_ratio: float, persistence: float, eps: float = SANITY_EPS_DEFAULT) -> Dict[str, Any]:
    upper_bound = 1.0 - dot_ratio + eps
    violation = max(0.0, persistence - upper_bound)
    ok = violation <= 0.0
    return {
        "eps": round(float(eps), 9),
        "invariant": "cycle_persistence_score <= 1 - dot_ratio + eps",
        "invariant_ok": bool(ok),
        "invariant_violation": round(float(violation), 9),
        "status": "OK" if ok else "WARN_INCONSISTENT",
        "possible_causes": []
        if ok
        else [
            "SCC/cycle detection mismatch",
            "Aliasing from coarse bucketing",
            "Persistence definition mismatch",
        ],
    }


def compute_cycle_candidates(
    events: List[Dict[str, Any]],
    *,
    top_k: int = 10,
    min_count: int = 3,
    min_order_invariance: float = 0.7,
    min_return_time_p50: float = 2.0,
    max_return_time_p50: float = 512.0,
) -> List[Dict[str, Any]]:
    """Find cycle candidates (mark-only) for consolidation.

    Candidates are deterministic and include structural stats only.
    """
    if not events:
        return []

    signatures = extract_signatures(events)
    n = len(signatures)
    nodes, edges, _edge_sets, counts = _build_graph(signatures)
    scc_nodes = _compute_scc_nodes(nodes, edges, counts)

    positions: Dict[str, List[int]] = defaultdict(list)
    for idx, sig in enumerate(signatures):
        positions[sig].append(idx)

    buckets_by_sig: Dict[str, Dict[str, Any]] = {}
    for event, sig in zip(events, signatures):
        if sig not in buckets_by_sig:
            buckets_by_sig[sig] = event.get("cycle_bucket") or build_cycle_bucket(event)

    candidates: List[Dict[str, Any]] = []

    for sig in sorted(counts.keys()):
        cnt = counts[sig]
        cycle_member = sig in scc_nodes and cnt >= 2
        if cnt < min_count or not cycle_member:
            continue

        idxs = positions[sig]
        gaps = [b - a for a, b in zip(idxs, idxs[1:]) if b > a]
        if not gaps:
            continue

        rt_p50 = float(median(gaps))
        if rt_p50 < min_return_time_p50 or rt_p50 > max_return_time_p50:
            continue

        oi = _signature_order_invariance(events, idxs)
        if oi < min_order_invariance:
            continue

        candidates.append(
            {
                "signature": sig,
                "counts": int(cnt),
                "cycle_member": True,
                "support_ratio": round(cnt / max(1, n), 6),
                "return_time_mean": round(float(mean(gaps)), 6),
                "return_time_p50": round(rt_p50, 6),
                "order_invariance_score": round(float(oi), 6),
                "prototype_bucket": buckets_by_sig.get(sig, {}),
            }
        )

    candidates.sort(
        key=lambda x: (
            -int(x.get("counts", 0)),
            -float(x.get("order_invariance_score", 0.0)),
            float(x.get("return_time_p50", 0.0)),
            str(x.get("signature", "")),
        )
    )
    return candidates[: max(0, int(top_k))]


def compute_cycle_metrics(events: List[Dict[str, Any]], *, eps: float = SANITY_EPS_DEFAULT) -> Dict[str, Any]:
    n = len(events)
    if n == 0:
        empty_sanity = compute_cycle_sanity(0.0, 0.0, eps=eps)
        return {
            "events": 0,
            "dot_ratio": 0.0,
            "cycle_persistence_score": 0.0,
            "return_time_mean": 0.0,
            "return_time_p50": 0.0,
            "return_time_p95": 0.0,
            "order_invariance_score": 0.0,
            "order_invariance_action_multiset": 0.0,
            "order_invariance_goal_closure": 0.0,
            "obstruction_count": 0,
            "max_out_degree": 0,
            "branching_nodes_ratio": 0.0,
            "unique_nodes": 0,
            "unique_edges": 0,
            "dominant_cycles_topK": [],
            "sanity": empty_sanity,
        }

    signatures = extract_signatures(events)
    nodes, edges, edge_sets, counts = _build_graph(signatures)

    dot_ratio = sum(1 for s in signatures if counts[s] == 1) / n

    scc_nodes = _compute_scc_nodes(nodes, edges, counts)
    persistence = sum(1 for s in signatures if s in scc_nodes) / n

    gaps = _return_times(signatures)
    if gaps:
        p95_index = max(0, math.ceil(0.95 * len(gaps)) - 1)
        sorted_gaps = sorted(gaps)
        rt_mean = round(mean(gaps), 6)
        rt_p50 = round(float(median(gaps)), 6)
        rt_p95 = round(float(sorted_gaps[p95_index]), 6)
    else:
        rt_mean = rt_p50 = rt_p95 = 0.0

    max_out_degree = max((len(v) for v in edge_sets.values()), default=0)
    branching_nodes = sum(1 for v in edge_sets.values() if len(v) >= 3)

    metrics = {
        "events": n,
        "dot_ratio": round(dot_ratio, 6),
        "cycle_persistence_score": round(persistence, 6),
        "return_time_mean": rt_mean,
        "return_time_p50": rt_p50,
        "return_time_p95": rt_p95,
        "order_invariance_score": 0.0,
        "order_invariance_action_multiset": 0.0,
        "order_invariance_goal_closure": 0.0,
        "obstruction_count": _obstruction_count(signatures),
        "max_out_degree": int(max_out_degree),
        "branching_nodes_ratio": round(branching_nodes / max(1, len(nodes)), 6),
        "unique_nodes": int(len(nodes)),
        "unique_edges": int(sum(len(v) for v in edge_sets.values())),
        "dominant_cycles_topK": _dominant_transitions(signatures, topk=5),
    }

    oi_action, oi_goal, oi_score = _compute_order_invariance_decomposed(events, signatures)
    metrics["order_invariance_action_multiset"] = oi_action
    metrics["order_invariance_goal_closure"] = oi_goal
    metrics["order_invariance_score"] = oi_score

    metrics["sanity"] = compute_cycle_sanity(metrics["dot_ratio"], metrics["cycle_persistence_score"], eps=eps)
    return metrics


@dataclass
class CycleReport:
    run_id: str
    metrics: Dict[str, Any]
    paths: Dict[str, str]


def render_cycle_markdown(run_id: str, metrics: Dict[str, Any]) -> str:
    sanity = metrics.get("sanity") or {}

    lines = [
        f"# Cycle Report · {run_id}",
        "",
        "## Core Metrics",
        "",
        f"- dot_ratio: `{metrics.get('dot_ratio', 0.0):.6f}`",
        f"- cycle_persistence_score: `{metrics.get('cycle_persistence_score', 0.0):.6f}`",
        f"- return_time_mean/p50/p95: `{metrics.get('return_time_mean', 0.0):.3f}` / `{metrics.get('return_time_p50', 0.0):.3f}` / `{metrics.get('return_time_p95', 0.0):.3f}`",
        f"- order_invariance_score: `{metrics.get('order_invariance_score', 0.0):.6f}`",
        f"- order_invariance_action_multiset: `{metrics.get('order_invariance_action_multiset', 0.0):.6f}`",
        f"- order_invariance_goal_closure: `{metrics.get('order_invariance_goal_closure', 0.0):.6f}`",
        f"- obstruction_count: `{metrics.get('obstruction_count', 0)}`",
        "",
        "## Sanity Check",
        "",
        f"- invariant: `{sanity.get('invariant', 'cycle_persistence_score <= 1 - dot_ratio + eps')}`",
        f"- status: `{sanity.get('status', 'OK')}`",
        f"- invariant_ok: `{sanity.get('invariant_ok', True)}`",
        f"- invariant_violation: `{float(sanity.get('invariant_violation', 0.0)):.9f}`",
    ]

    if sanity.get("status") == "WARN_INCONSISTENT":
        lines.extend(
            [
                "",
                "⚠️ Inconsistency detected. Possible causes:",
                "",
                "- SCC/cycle detection mismatch",
                "- Aliasing from coarse bucketing",
                "- Persistence definition mismatch",
            ]
        )

    lines.extend(
        [
            "",
            "## Aliasing Diagnostics",
            "",
            f"- unique_nodes: `{metrics.get('unique_nodes', 0)}`",
            f"- unique_edges: `{metrics.get('unique_edges', 0)}`",
            f"- max_out_degree: `{metrics.get('max_out_degree', 0)}`",
            f"- branching_nodes_ratio: `{metrics.get('branching_nodes_ratio', 0.0):.6f}`",
            "",
            "Interpretation:",
            "- Higher obstruction/branching can mean real overlap conflicts,",
            "  but can also be caused by coarse bucket quantization (aliasing).",
            "",
            "## Dominant Transitions (Top-5)",
            "",
        ]
    )
    for row in metrics.get("dominant_cycles_topK", []):
        lines.append(f"- `{row.get('from')}` → `{row.get('to')}` · count={row.get('count')}")
    if not metrics.get("dominant_cycles_topK"):
        lines.append("- (none)")

    candidates = metrics.get("cycle_candidates_topK") or []
    lines.extend(["", "## Cycle Candidates (Top-K)", ""])
    if candidates:
        for c in candidates:
            lines.append(
                "- `{sig}` · count={cnt} · p50={p50:.3f} · OI={oi:.3f}".format(
                    sig=c.get("signature", "?"),
                    cnt=int(c.get("counts", 0)),
                    p50=float(c.get("return_time_p50", 0.0)),
                    oi=float(c.get("order_invariance_score", 0.0)),
                )
            )
    else:
        lines.append("- (none)")

    lines.append("")
    return "\n".join(lines)
