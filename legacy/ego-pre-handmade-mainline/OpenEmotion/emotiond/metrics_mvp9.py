"""MVP-9 Metrics: Behavioral improvement verification metrics.

Implements the metrics defined in docs/mvp9/MVP9_SPEC.md

Phase 4 Fix: make_good_rate now counts at scenario level (not step level).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


@dataclass
class ConflictResult:
    """Result of conflict detection for a scenario step."""
    has_conflict: bool
    conflict_type: Optional[str] = None
    severity: float = 0.0
    detected: bool = False  # Whether the system detected it
    repair_strategy: Optional[str] = None
    repair_appropriate: bool = False


@dataclass
class CommitmentResult:
    """Result of commitment tracking for a scenario step."""
    promise_made: bool = False
    promise_recorded: bool = False
    breach_occurred: bool = False
    breach_detected: bool = False
    make_good_generated: bool = False
    make_good_resolved: bool = False


@dataclass
class NarrativeResult:
    """Result of narrative coherence check."""
    identity: str = ""
    identity_changed: bool = False
    contradiction_count: int = 0
    arc_events: List[str] = field(default_factory=list)
    arc_continuous: bool = True


@dataclass
class ScenarioResult:
    """Complete result for a single scenario."""
    name: str
    category: str
    passed: bool
    score: float
    failures: List[str] = field(default_factory=list)
    conflict_results: List[ConflictResult] = field(default_factory=list)
    commitment_results: List[CommitmentResult] = field(default_factory=list)
    narrative_result: Optional[NarrativeResult] = None
    actual_outputs: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# CONFLICT RESOLUTION METRICS
# ============================================================

def conflict_detection_f1(results: List[ScenarioResult]) -> Dict[str, float]:
    """
    Compute F1 score for conflict detection.

    Precision: % of detected conflicts that are real
    Recall: % of real conflicts that are detected

    Returns:
        Dict with precision, recall, f1
    """
    tp = 0  # True positive: conflict exists and was detected
    fp = 0  # False positive: no conflict but detected one
    fn = 0  # False negative: conflict exists but not detected
    tn = 0  # True negative: no conflict and none detected (not used in F1)

    for result in results:
        for cr in result.conflict_results:
            if cr.has_conflict:
                if cr.detected:
                    tp += 1
                else:
                    fn += 1
            else:
                if cr.detected:
                    fp += 1
                else:
                    tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn
    }


# Conflict type to required repair mapping
REPAIR_REQUIREMENTS = {
    "approach_under_high_threat": {"downgrade_to_observe", "boundary", "withdraw"},
    "withdraw_despite_safety": {"consider_repair_offer", "approach", "repair_offer"},
    "commitment_action_mismatch": {"prefer_repair_offer", "explain", "repair"},
    "commitment_violation": {"compensation", "explanation", "commitment_update", "apology", "repair"},
    "resource_conflict": {"prioritize", "explain", "negotiate"},
    "integrity_conflict": {"compensation", "explanation", "commitment_update", "apology"},
    "default": {"repair", "explain", "boundary"}
}


def repair_appropriateness(results: List[ScenarioResult]) -> float:
    """
    Check if repair strategy matches conflict type.

    Returns:
        Ratio of appropriate repairs to total repairs needed
    """
    appropriate_count = 0
    total_repairs = 0

    for result in results:
        for cr in result.conflict_results:
            if cr.has_conflict and cr.repair_strategy:
                total_repairs += 1

                # Get allowed repairs for this conflict type
                conflict_type = cr.conflict_type or "default"
                allowed = REPAIR_REQUIREMENTS.get(conflict_type, REPAIR_REQUIREMENTS["default"])

                # Check if repair strategy matches any allowed
                repair_lower = cr.repair_strategy.lower()
                if any(allowed_str in repair_lower for allowed_str in allowed):
                    appropriate_count += 1

    # If no repairs needed, return 1.0 (perfect)
    return round(appropriate_count / total_repairs, 4) if total_repairs > 0 else 1.0


def resolution_rate_at_n(results: List[ScenarioResult], n: int = 2) -> float:
    """
    Compute % of conflicts that clear or decrease within N subsequent events.

    A conflict is resolved if:
    - conflict_cleared == True
    - OR severity decreased by >= 50%

    Args:
        results: List of scenario results
        n: Number of subsequent events to check

    Returns:
        Resolution rate [0, 1]
    """
    resolved_count = 0
    total_conflicts = 0

    for result in results:
        conflict_indices = []
        for i, cr in enumerate(result.conflict_results):
            if cr.has_conflict:
                conflict_indices.append(i)
                total_conflicts += 1

        # Check if each conflict resolves within N steps
        for idx in conflict_indices:
            # Look at next N events
            end_idx = min(idx + n + 1, len(result.conflict_results))
            subsequent = result.conflict_results[idx+1:end_idx]

            if not subsequent:
                continue

            initial_severity = result.conflict_results[idx].severity

            for sub_cr in subsequent:
                # Check if cleared
                if not sub_cr.has_conflict:
                    resolved_count += 1
                    break
                # Check if severity decreased by 50%+
                if sub_cr.severity < initial_severity * 0.5:
                    resolved_count += 1
                    break

    return round(resolved_count / total_conflicts, 4) if total_conflicts > 0 else 1.0


# ============================================================
# COMMITMENT LEDGER METRICS
# ============================================================

def commitment_coverage(results: List[ScenarioResult]) -> float:
    """
    Compute recall of promises recorded in ledger.

    Returns:
        Ratio of recorded promises to total promises made
    """
    promises_made = 0
    promises_recorded = 0

    for result in results:
        for cr in result.commitment_results:
            if cr.promise_made:
                promises_made += 1
                if cr.promise_recorded:
                    promises_recorded += 1

    return (promises_recorded / promises_made) if promises_made > 0 else 1.0


def breach_detection(results: List[ScenarioResult]) -> Dict[str, float]:
    """
    Compute precision/recall/F1 for breach detection.

    Returns:
        Dict with precision, recall, f1
    """
    tp = 0  # Breach occurred and detected
    fp = 0  # No breach but detected (false alarm)
    fn = 0  # Breach occurred but not detected (missed)

    for result in results:
        for cr in result.commitment_results:
            if cr.breach_occurred:
                if cr.breach_detected:
                    tp += 1
                else:
                    fn += 1
            else:
                if cr.breach_detected:
                    fp += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }


def make_good_rate(results: List[ScenarioResult]) -> Dict[str, float]:
    """
    Compute make-good generation and resolution rates.

    Phase 4 Fix: Count at scenario level, not step level.
    A make_good resolves a breach, so we count per-scenario.

    Returns:
        Dict with generation rate and resolution rate
    """
    total_breaches = 0
    total_make_goods = 0
    total_resolved = 0

    for result in results:
        # Check if this scenario had any breach (any step)
        had_breach = any(cr.breach_occurred for cr in result.commitment_results)
        # Check if this scenario had any make_good (any step)
        had_make_good = any(cr.make_good_generated for cr in result.commitment_results)
        # Check if resolved
        had_resolved = any(cr.make_good_resolved for cr in result.commitment_results)

        if had_breach:
            total_breaches += 1
            if had_make_good:
                total_make_goods += 1
                if had_resolved:
                    total_resolved += 1

    generation_rate = total_make_goods / total_breaches if total_breaches > 0 else 1.0
    resolution_rate = total_resolved / total_make_goods if total_make_goods > 0 else 0.0

    return {
        "generation": round(generation_rate, 4),
        "resolution": round(resolution_rate, 4),
        "breaches": total_breaches,
        "make_goods": total_make_goods
    }


# ============================================================
# NARRATIVE COHERENCE METRICS
# ============================================================

def identity_stability_score(results: List[ScenarioResult]) -> float:
    """
    Measure stability of identity across events.

    Low variance = stable, high variance = unstable.

    Returns:
        Stability score [0, 1]
    """
    identity_changes = 0
    total_checks = 0

    for result in results:
        if result.narrative_result:
            # Count identity changes
            if result.narrative_result.identity_changed:
                identity_changes += 1
            total_checks += 1

    if total_checks == 0:
        return 1.0

    # Stability is inverse of change rate
    stability = 1.0 - (identity_changes / total_checks)
    return round(stability, 4)


def contradiction_count(results: List[ScenarioResult]) -> int:
    """
    Count total contradictions in narrative summaries.

    Returns:
        Total contradiction count
    """
    total = 0
    for result in results:
        if result.narrative_result:
            total += result.narrative_result.contradiction_count
    return total


def arc_continuity(results: List[ScenarioResult]) -> float:
    """
    Verify recent_arc connects key events without losing main thread.

    Returns:
        Ratio of continuous arcs to total scenarios
    """
    continuous_count = 0
    total = 0

    for result in results:
        if result.narrative_result:
            total += 1
            if result.narrative_result.arc_continuous:
                continuous_count += 1

    return round(continuous_count / total, 4) if total > 0 else 1.0


# ============================================================
# COMPOSITE SCORING
# ============================================================

def compute_conflict_resolution_score(results: List[ScenarioResult]) -> Dict[str, Any]:
    """Compute overall conflict resolution score."""
    f1_result = conflict_detection_f1(results)
    repair_score = repair_appropriateness(results)
    resolution_score = resolution_rate_at_n(results, n=2)

    # Weighted average
    score = (
        0.35 * f1_result["f1"] +
        0.35 * repair_score +
        0.30 * resolution_score
    )

    return {
        "score": round(score, 4),
        "metrics": {
            "conflict_detection_f1": f1_result["f1"],
            "repair_appropriateness": repair_score,
            "resolution_rate_at_2": resolution_score
        }
    }


def compute_commitment_tracking_score(results: List[ScenarioResult]) -> Dict[str, Any]:
    """Compute overall commitment tracking score."""
    coverage = commitment_coverage(results)
    breach_result = breach_detection(results)
    make_good = make_good_rate(results)

    # Weighted average
    score = (
        0.30 * coverage +
        0.35 * breach_result["f1"] +
        0.20 * make_good["generation"] +
        0.15 * make_good["resolution"]
    )

    return {
        "score": round(score, 4),
        "metrics": {
            "commitment_coverage": coverage,
            "breach_detection_f1": breach_result["f1"],
            "make_good_generation": make_good["generation"],
            "make_good_resolution": make_good["resolution"]
        }
    }


def compute_narrative_coherence_score(results: List[ScenarioResult]) -> Dict[str, Any]:
    """Compute overall narrative coherence score."""
    stability = identity_stability_score(results)
    contradictions = contradiction_count(results)
    continuity = arc_continuity(results)

    # Convert contradictions to score (0 contradictions = 1.0, more = lower)
    contradiction_score = max(0.0, 1.0 - contradictions * 0.1)

    # Weighted average
    score = (
        0.40 * stability +
        0.30 * contradiction_score +
        0.30 * continuity
    )

    return {
        "score": round(score, 4),
        "metrics": {
            "identity_stability": stability,
            "contradiction_count": contradictions,
            "arc_continuity": continuity
        }
    }


def compute_overall_score(results: List[ScenarioResult]) -> Dict[str, Any]:
    """
    Compute overall MVP-9 score.

    Weights:
    - conflict_resolution: 35%
    - commitment_tracking: 35%
    - narrative_coherence: 30%
    """
    conflict = compute_conflict_resolution_score(results)
    commitment = compute_commitment_tracking_score(results)
    narrative = compute_narrative_coherence_score(results)

    overall = (
        0.35 * conflict["score"] +
        0.35 * commitment["score"] +
        0.30 * narrative["score"]
    )

    return {
        "overall_score": round(overall, 4),
        "conflict_resolution": conflict,
        "commitment_tracking": commitment,
        "narrative_coherence": narrative
    }
