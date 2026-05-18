"""DMN cycle-driven autonomy suggestions for MVP11.4.

Generates low-weight suggestions only (no direct execution path).
"""

from __future__ import annotations

from typing import Any, Dict, List

from .homeostasis import HomeostasisState


def _hs_dict(homeostasis: HomeostasisState | Dict[str, Any] | None) -> Dict[str, float]:
    if isinstance(homeostasis, HomeostasisState):
        return {k: float(v) for k, v in homeostasis.to_dict().items()}
    if isinstance(homeostasis, dict):
        return {k: float(v) for k, v in homeostasis.items() if isinstance(v, (int, float))}
    return {}


def _expected_hs_delta(hs: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    # lightweight heuristic for explainability (not execution binding)
    if hs.get("energy", 0.5) < 0.45:
        out["energy"] = 0.05
    if hs.get("certainty", 0.5) < 0.45:
        out["certainty"] = 0.05
    if hs.get("safety", 0.5) < 0.45:
        out["safety"] = 0.04
    return out


def propose_suggestions(
    homeostasis: HomeostasisState | Dict[str, Any] | None,
    cycle_graph: Dict[str, Any] | None,
    cycle_store: Dict[str, Any] | None,
    *,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Produce non-executing autonomy suggestions from cycle memory.

    Each suggestion is advisory and must still pass EFE/Planner/Governor chain.
    """
    hs = _hs_dict(homeostasis)
    graph = cycle_graph or {}
    store = cycle_store or {}

    items = list((store.get("items") or []))
    if not items:
        return []

    # prioritize by cycle support and graph transition salience
    edge_rank = {(e.get("to"), e.get("from")): float(e.get("count", 0)) for e in (graph.get("top_edges") or [])}

    scored = []
    for item in items:
        sig = str(item.get("signature", ""))
        stats = item.get("stats") or {}
        proto = item.get("prototype_bucket") or {}

        score = float(stats.get("counts", 0) or 0) * 0.6 + float(stats.get("order_invariance_score", 0) or 0) * 2.0
        for (to_sig, _from_sig), cnt in edge_rank.items():
            if to_sig == sig:
                score += 0.2 * cnt

        scored.append((score, sig, proto, item))

    scored.sort(key=lambda x: (-x[0], x[1]))

    suggestions: List[Dict[str, Any]] = []
    for _score, sig, proto, item in scored[: max(1, int(limit))]:
        psi = proto.get("psi") or {}
        action_type = psi.get("action_type") or proto.get("action_type")
        focus = psi.get("focus") or proto.get("focus")
        intent = psi.get("intent") or proto.get("intent")

        suggestion = {
            "focus": focus,
            "intent": intent,
            "action_type": action_type,
            "plan_template_hash": item.get("plan_template_hash"),
            "weight": 0.1,  # intentionally low-weight
            "reason": "cycle_autonomy_prior",
            "cycle_refs": [sig],
            "expected_hs_delta": _expected_hs_delta(hs),
        }
        suggestions.append(suggestion)

    return suggestions


def build_autonomy_ledger_entry(
    suggestions: List[Dict[str, Any]],
    *,
    reason: str = "dmn_cycle_rollout",
) -> Dict[str, Any]:
    """Build auditable payload for ledger/logging layers."""
    return {
        "reason": reason,
        "suggestions": suggestions,
        "cycle_refs": [ref for s in suggestions for ref in (s.get("cycle_refs") or [])],
        "expected_hs_delta": [s.get("expected_hs_delta") or {} for s in suggestions],
    }
