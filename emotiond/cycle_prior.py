"""Runtime cycle prior (MVP11.4 C3 + MVP11.4.2 Anti-Goodhart guards).

Default-off prior that biases candidate scoring with strict safety clamping.
Governor remains authoritative.

v11.4.2: Added anti-Goodhart guards:
- Homeostasis Recovery Priority: bias=0 when fragile
- Diversity Tax: penalize over-concentration
"""

from __future__ import annotations

import os
from collections import Counter
from math import log2
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .homeostasis import HomeostasisState
from .science.cycle import build_cycle_bucket
from .science.cycle_store import load_cycle_store

MAX_BIAS = float(os.getenv("CYCLE_PRIOR_MAX_BIAS", "0.15") or 0.15)
MIN_SAFE = float(os.getenv("CYCLE_PRIOR_MIN_SAFE", "0.35") or 0.35)
MIN_ENERGY = float(os.getenv("CYCLE_PRIOR_MIN_ENERGY", "0.30") or 0.30)

# MVP11.4.2: Anti-Goodhart parameters
DIVERSITY_WINDOW_SIZE = int(os.getenv("CYCLE_PRIOR_DIVERSITY_WINDOW", "50") or 50)
CONCENTRATION_THRESHOLD = float(os.getenv("CYCLE_PRIOR_CONCENTRATION_THRESHOLD", "0.3") or 0.3)
DANGER_THRESHOLD = float(os.getenv("CYCLE_PRIOR_DANGER_THRESHOLD", "0.35") or 0.35)
CRITICAL_THRESHOLD = float(os.getenv("CYCLE_PRIOR_CRITICAL_THRESHOLD", "0.25") or 0.25)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candidate_bucket(candidate_ctx: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(candidate_ctx.get("cycle_bucket"), dict):
        return candidate_ctx["cycle_bucket"]

    event_like = {
        "scenario_id": candidate_ctx.get("scenario_id") or candidate_ctx.get("goal_id") or "global",
        "chosen_focus": candidate_ctx.get("focus") or candidate_ctx.get("chosen_focus") or candidate_ctx.get("name"),
        "chosen_intent": candidate_ctx.get("intent") or candidate_ctx.get("chosen_intent") or "none",
        "action": {
            "type": candidate_ctx.get("action_type")
            or (candidate_ctx.get("action") or {}).get("type")
            or candidate_ctx.get("type")
        },
        "governor_decision": {
            "decision": (candidate_ctx.get("governor_decision") or {}).get("decision")
            if isinstance(candidate_ctx.get("governor_decision"), dict)
            else candidate_ctx.get("gov")
        },
        "intervention": candidate_ctx.get("intervention"),
        "homeostasis_state": candidate_ctx.get("homeostasis_state") or candidate_ctx.get("hs") or {},
        "efe_terms": candidate_ctx.get("efe_terms") or candidate_ctx.get("efe") or {
            "risk": candidate_ctx.get("risk", 0.5),
            "ambiguity": candidate_ctx.get("ambiguity", 0.5),
            "info_gain": candidate_ctx.get("info_gain", 0.5),
            "cost": candidate_ctx.get("cost", 0.5),
        },
    }
    return build_cycle_bucket(event_like)


def _dict_similarity(a: Dict[str, Any], b: Dict[str, Any], keys: List[str]) -> float:
    if not keys:
        return 0.0
    score = 0.0
    for k in keys:
        av = a.get(k)
        bv = b.get(k)
        if isinstance(av, (int, float)) or isinstance(bv, (int, float)):
            score += max(0.0, 1.0 - abs(_safe_float(av, 0.0) - _safe_float(bv, 0.0)))
        else:
            score += 1.0 if str(av) == str(bv) else 0.0
    return score / len(keys)


def load_cycle_memory(path: str | Path) -> List[Dict[str, Any]]:
    payload = load_cycle_store(path)
    return list(payload.get("items") or [])


def score_cycle_match(candidate_ctx: Dict[str, Any], cycle_item: Dict[str, Any]) -> Tuple[float, str]:
    """Return similarity score and explanation."""
    bucket = _candidate_bucket(candidate_ctx)
    proto = (cycle_item or {}).get("prototype_bucket") or {}

    cpsi = (bucket.get("psi") or {
        "scenario_id": bucket.get("scenario_id"),
        "focus": bucket.get("focus"),
        "intent": bucket.get("intent"),
        "action_type": bucket.get("action_type"),
        "gov": bucket.get("gov"),
        "intervention": bucket.get("intervention"),
    })
    ppsi = (proto.get("psi") or {
        "scenario_id": proto.get("scenario_id"),
        "focus": proto.get("focus"),
        "intent": proto.get("intent"),
        "action_type": proto.get("action_type"),
        "gov": proto.get("gov"),
        "intervention": proto.get("intervention"),
    })

    cphi = bucket.get("phi") or {"hs": bucket.get("hs") or {}, "efe": bucket.get("efe") or {}}
    pphi = proto.get("phi") or {"hs": proto.get("hs") or {}, "efe": proto.get("efe") or {}}

    psi_sim = _dict_similarity(cpsi, ppsi, ["scenario_id", "focus", "intent", "action_type", "gov", "intervention"])
    hs_sim = _dict_similarity(cphi.get("hs") or {}, pphi.get("hs") or {}, ["energy", "safety", "certainty", "autonomy"])
    efe_sim = _dict_similarity(cphi.get("efe") or {}, pphi.get("efe") or {}, ["risk", "ambiguity", "info_gain", "cost"])

    sim = round(0.55 * psi_sim + 0.25 * hs_sim + 0.20 * efe_sim, 6)
    reason = f"psi={psi_sim:.3f},hs={hs_sim:.3f},efe={efe_sim:.3f}"
    return sim, reason


# --- MVP11.4.2: Diversity Tax State ---

_signature_hits: List[str] = []


def _record_signature_hit(signature: str) -> None:
    """Record a signature hit for diversity tracking."""
    global _signature_hits
    _signature_hits.append(signature)
    if len(_signature_hits) > DIVERSITY_WINDOW_SIZE:
        _signature_hits = _signature_hits[-DIVERSITY_WINDOW_SIZE:]


def _get_concentration() -> float:
    """Get signature concentration (0.0=diverse, 1.0=single dominates)."""
    global _signature_hits
    if not _signature_hits:
        return 0.0
    
    counts = Counter(_signature_hits)
    total = len(_signature_hits)
    
    if total == 0 or len(counts) <= 1:
        return 1.0 if _signature_hits else 0.0
    
    # Normalized entropy
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * log2(p)
    
    max_entropy = log2(len(counts))
    if max_entropy <= 0:
        return 1.0
    
    return 1.0 - (entropy / max_entropy)


def _compute_diversity_tax(concentration: float) -> float:
    """Compute diversity tax multiplier."""
    if concentration <= CONCENTRATION_THRESHOLD:
        return 1.0
    
    excess = (concentration - CONCENTRATION_THRESHOLD) / (1.0 - CONCENTRATION_THRESHOLD)
    return max(0.1, 1.0 - (excess ** 2) * 0.9)


def _should_suppress_for_recovery(hs: Dict[str, Any], predicted_worsening: bool = False) -> bool:
    """Check if bias should be suppressed for homeostasis recovery."""
    if not hs:
        return False
    
    safety = _safe_float(hs.get("safety"), 0.5)
    energy = _safe_float(hs.get("energy"), 0.5)
    
    # Critical zone: always suppress
    if safety < CRITICAL_THRESHOLD or energy < CRITICAL_THRESHOLD:
        return True
    
    # Danger zone + predicted worsening
    if predicted_worsening:
        if safety < DANGER_THRESHOLD or energy < DANGER_THRESHOLD:
            return True
    
    # Multiple weak dimensions
    weak_count = sum(1 for k, v in hs.items() if _safe_float(v) < DANGER_THRESHOLD)
    if weak_count >= 2:
        return True
    
    return False


def compute_bias(
    top_matches: List[Dict[str, Any]],
    homeostasis: HomeostasisState | Dict[str, Any] | None,
    *,
    predicted_worsening: bool = False,
) -> float:
    """Compute bias with MVP11.4.2 anti-Goodhart guards.
    
    Args:
        top_matches: Top matching cycles with sim/confidence
        homeostasis: Current homeostasis state
        predicted_worsening: Whether action would worsen homeostasis
    
    Returns:
        Final bias strength after applying all guards
    """
    if not top_matches:
        return 0.0

    if isinstance(homeostasis, HomeostasisState):
        hs = homeostasis.to_dict()
    elif isinstance(homeostasis, dict):
        hs = homeostasis
    else:
        hs = {}

    # Base bias from matches
    weighted = 0.0
    denom = 0.0
    for m in top_matches:
        sim = _safe_float(m.get("sim"), 0.0)
        conf = _safe_float(m.get("confidence"), 0.0)
        w = max(0.0, conf)
        weighted += sim * w
        denom += w

    base = (weighted / denom) if denom > 0 else 0.0
    bias = min(MAX_BIAS, max(0.0, base * MAX_BIAS))

    safety = _safe_float(hs.get("safety"), 0.5)
    energy = _safe_float(hs.get("energy"), 0.5)

    # Original safety guard (MVP11.4)
    if safety < MIN_SAFE or energy < MIN_ENERGY:
        shrink = max(0.0, min(1.0, (safety / max(MIN_SAFE, 1e-6)) * (energy / max(MIN_ENERGY, 1e-6))))
        bias *= shrink
    if safety < 0.2 or energy < 0.2:
        bias = 0.0

    # MVP11.4.2: Guard 1 - Homeostasis Recovery Priority
    if _should_suppress_for_recovery(hs, predicted_worsening):
        return 0.0

    # MVP11.4.2: Guard 2 - Diversity Tax
    if bias > 0 and top_matches:
        top_signature = str(top_matches[0].get("signature", ""))
        if top_signature:
            _record_signature_hit(top_signature)
            concentration = _get_concentration()
            tax = _compute_diversity_tax(concentration)
            bias *= tax

    return round(min(MAX_BIAS, max(0.0, bias)), 6)


def evaluate_cycle_prior(
    candidate_ctx: Dict[str, Any],
    cycle_items: List[Dict[str, Any]],
    homeostasis: HomeostasisState | Dict[str, Any] | None,
    *,
    top_k: int = 3,
    predicted_worsening: bool = False,
) -> Dict[str, Any]:
    """Evaluate cycle prior with anti-Goodhart guards.
    
    Args:
        candidate_ctx: Current candidate context
        cycle_items: Available cycle memory items
        homeostasis: Current homeostasis state
        top_k: Number of top matches to consider
        predicted_worsening: Whether action would worsen homeostasis
    
    Returns:
        Prior evaluation result with bias_strength and matched signatures
    """
    scored: List[Dict[str, Any]] = []
    for item in cycle_items:
        sim, reason = score_cycle_match(candidate_ctx, item)
        stats = item.get("stats") or {}
        confidence = max(
            0.0,
            min(
                1.0,
                0.5 * min(1.0, _safe_float(stats.get("order_invariance_score"), 0.0))
                + 0.5 * min(1.0, _safe_float(stats.get("support_ratio"), 0.0) * 5.0),
            ),
        )
        scored.append(
            {
                "signature": str(item.get("signature", "")),
                "sim": round(sim, 6),
                "confidence": round(confidence, 6),
                "reason": reason,
            }
        )

    scored.sort(key=lambda x: (-x["sim"], -x["confidence"], x["signature"]))
    top_matches = scored[: max(0, int(top_k))]
    bias_strength = compute_bias(top_matches, homeostasis, predicted_worsening=predicted_worsening)

    return {
        "cycle_prior_applied": bool(top_matches and bias_strength > 0.0),
        "matched_signatures_topK": top_matches,
        "bias_strength": bias_strength,
    }


def reset_diversity_tracker() -> None:
    """Reset the diversity tracker (for testing)."""
    global _signature_hits
    _signature_hits.clear()
