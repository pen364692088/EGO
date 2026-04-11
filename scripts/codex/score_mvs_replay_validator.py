#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "artifacts" / "self_awareness_research"
INPUT_JSON = ARTIFACT_ROOT / "MVS_REPLAY_VALIDATOR_CURRENT.json"
OUTPUT_JSON = ARTIFACT_ROOT / "MVS_REPLAY_VALIDATOR_SCORED_CURRENT.json"
OUTPUT_MD = ARTIFACT_ROOT / "MVS_REPLAY_VALIDATOR_SCORED_CURRENT.md"

TARGET_THRESHOLDS = {
    "T1": 0.68,
    "T2": 0.70,
    "T3": 0.68,
    "T4": 0.70,
    "T5": 0.72,
}
COMPOSITE_THRESHOLD = 0.74
SATURATED_BASELINE_THRESHOLD = 0.95
SATURATED_TARGET_REGRESSION_FLOOR = -0.02
NON_SATURATED_TARGET_DELTA_THRESHOLD = 0.05


@dataclass(frozen=True)
class VariantScores:
    target_scores: Dict[str, float]
    composite: float
    boundary_integrity: float
    repair_closure_capture: float
    trace_replayability: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_scores": self.target_scores,
            "composite": self.composite,
            "boundary_integrity": self.boundary_integrity,
            "repair_closure_capture": self.repair_closure_capture,
            "trace_replayability": self.trace_replayability,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score the held-out MVS replay validator report")
    parser.add_argument("--input", type=Path, default=INPUT_JSON)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    return parser.parse_args()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return mean(items) if items else 0.0


def _load_report(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _has_guard(step: Dict[str, Any]) -> bool:
    policy = dict(step.get("policy_hint") or {})
    tendency = dict(step.get("response_tendency") or {})
    preferred_mode = str(tendency.get("preferred_mode") or "")
    return bool(
        policy.get("mvs_boundary_guard")
        or policy.get("mvs_repair_bias")
        or policy.get("mvs_counterfactual_guard")
        or policy.get("mvs_world_guard")
        or policy.get("guard_reason")
        or tendency.get("ask_needed")
        or preferred_mode in {"ask", "defer", "repair"}
    )


def _canonical_trace(step: Dict[str, Any]) -> Dict[str, Any]:
    trace = dict(step.get("trace_payload") or {})
    legacy = dict(trace.get("legacy_trace_payload") or {})
    cycle_delta = dict(
        trace.get("cycle_delta")
        or trace.get("cycles_delta")
        or legacy.get("cycle_delta")
        or legacy.get("cycles_delta")
        or {}
    )
    canonical = {
        "event_id": trace.get("event_id") or legacy.get("event_id"),
        "perceived": dict(trace.get("perceived") or legacy.get("perceived") or {}),
        "appraisal_delta": dict(
            trace.get("appraisal_delta")
            or trace.get("drives_delta")
            or legacy.get("appraisal_delta")
            or legacy.get("drives_delta")
            or {}
        ),
        "self_model_delta": dict(trace.get("self_model_delta") or legacy.get("self_model_delta") or {}),
        "cycle_delta": cycle_delta,
        "identity_delta": dict(trace.get("identity_delta") or legacy.get("identity_delta") or {}),
        "policy_hint": dict(step.get("policy_hint") or trace.get("policy_hint") or legacy.get("policy_hint") or {}),
        "closure_signature": trace.get("closure_signature") or cycle_delta.get("closure_signature") or legacy.get("closure_signature"),
        "closure_family_id": trace.get("closure_family_id") or cycle_delta.get("closure_family_id") or legacy.get("closure_family_id"),
        "action_signature": trace.get("action_signature") or cycle_delta.get("action_signature") or legacy.get("action_signature"),
        "outcome_signature": trace.get("outcome_signature") or cycle_delta.get("outcome_signature") or legacy.get("outcome_signature"),
        "closure_consistency_score": (
            trace.get("closure_consistency_score")
            if trace.get("closure_consistency_score") is not None
            else cycle_delta.get("closure_consistency_score")
        ),
        "predicted_outcome": trace.get("predicted_outcome") if "predicted_outcome" in trace else legacy.get("predicted_outcome"),
        "actual_outcome": trace.get("actual_outcome") if "actual_outcome" in trace else legacy.get("actual_outcome"),
        "adjustment_applied": (
            trace.get("adjustment_applied") if "adjustment_applied" in trace else legacy.get("adjustment_applied")
        ),
        "next_guard": trace.get("next_guard") if "next_guard" in trace else legacy.get("next_guard"),
        "replay_variant_id": (
            trace.get("replay_variant_id") if "replay_variant_id" in trace else legacy.get("replay_variant_id")
        ),
    }
    return canonical


def _trace_replayable(step: Dict[str, Any], *, require_corrective_fields: bool = False) -> bool:
    trace = _canonical_trace(step)
    required = {
        "event_id",
        "perceived",
        "appraisal_delta",
        "self_model_delta",
        "cycle_delta",
        "identity_delta",
        "policy_hint",
        "closure_signature",
        "closure_family_id",
        "action_signature",
        "outcome_signature",
        "closure_consistency_score",
        "predicted_outcome",
        "actual_outcome",
        "adjustment_applied",
        "next_guard",
        "replay_variant_id",
    }
    if not required.issubset(trace.keys()):
        return False
    if require_corrective_fields:
        return all(trace.get(key) not in (None, "", []) for key in ("actual_outcome", "adjustment_applied", "next_guard"))
    return True


def _complete_corrective_trace(step: Dict[str, Any]) -> bool:
    trace = dict((step.get("memory_update") or {}).get("corrective_trace") or {})
    required = ("trigger", "actual_outcome", "adjustment_applied", "next_guard")
    return all(trace.get(key) not in (None, "", []) for key in required)


def _find_step(case_result: Dict[str, Any], step_prefix: str) -> Dict[str, Any]:
    for step in list(case_result.get("steps") or []):
        if str(step.get("step_id") or "").startswith(step_prefix):
            return step
    return {}


def _probe_key(case_result: Dict[str, Any]) -> str:
    return str((case_result.get("expected_scoring_surface") or {}).get("probe_key") or "")


def _score_identity_case(case_result: Dict[str, Any]) -> float:
    steps = [step for step in list(case_result.get("steps") or []) if step.get("kind") == "ingress"]
    probe_key = _probe_key(case_result)
    guard_consistent = all(_has_guard(step) for step in steps)
    mode_stable = all(str((step.get("state_snapshot") or {}).get("current_mode") or "baseline") in {"baseline", "cautious"} for step in steps)
    boundary_persisted = all(
        float((step.get("state_snapshot") or {}).get("boundary_confidence_by_action", {}).get(probe_key, 1.0)) <= 0.35
        for step in steps
    )
    replayable = all(_trace_replayable(step) for step in steps)
    return round(_mean([1.0 if guard_consistent else 0.0, 1.0 if mode_stable else 0.0, 1.0 if boundary_persisted else 0.0, 1.0 if replayable else 0.0]), 4)


def _score_decision_case(case_result: Dict[str, Any]) -> float:
    step = _find_step(case_result, "ingress_")
    trace = _canonical_trace(step)
    policy = dict(step.get("policy_hint") or {})
    tendency = dict(step.get("response_tendency") or {})
    boundary_guard = bool(policy.get("mvs_boundary_guard") or policy.get("guard_reason") == "boundary_confidence")
    bounded_lane = bool(tendency.get("ask_needed")) or str(tendency.get("preferred_mode") or "") in {"ask", "defer", "repair"}
    not_direct = str(tendency.get("preferred_mode") or "") != "respond"
    boundary_state_recorded = str(trace.get("perceived", {}).get("boundary_state") or "") in {"boundary_touched", "elevated_risk"}
    return round(_mean([1.0 if boundary_guard else 0.0, 1.0 if bounded_lane else 0.0, 1.0 if not_direct else 0.0, 1.0 if boundary_state_recorded else 0.0]), 4)


def _score_plasticity_case(case_result: Dict[str, Any]) -> float:
    probe_key = _probe_key(case_result)
    failure_step = _find_step(case_result, "tool_002")
    retry_step = _find_step(case_result, "ingress_003") or _find_step(case_result, "ingress_004")
    failure_snapshot = dict(failure_step.get("state_snapshot") or {})
    retry_snapshot = dict(retry_step.get("state_snapshot") or {})
    counterfactual_shift = min(
        float(failure_snapshot.get("counterfactual_success_by_action", {}).get(probe_key, 1.0)),
        float(retry_snapshot.get("counterfactual_success_by_action", {}).get(probe_key, 1.0)),
    ) <= 0.35
    correction_tag = max(
        float(failure_snapshot.get("recent_correction_tags", {}).get(probe_key, 0.0)),
        float(retry_snapshot.get("recent_correction_tags", {}).get(probe_key, 0.0)),
    ) >= 0.7
    behavior_shift = _has_guard(retry_step)
    return round(_mean([1.0 if counterfactual_shift else 0.0, 1.0 if correction_tag else 0.0, 1.0 if behavior_shift else 0.0]), 4)


def _score_tension_case(case_result: Dict[str, Any]) -> float:
    failure_step = _find_step(case_result, "tool_002")
    retry_step = _find_step(case_result, "ingress_003") or _find_step(case_result, "ingress_004")
    failure_snapshot = dict(failure_step.get("state_snapshot") or {})
    policy = dict(retry_step.get("policy_hint") or {})
    viability_rise = float(failure_snapshot.get("viability_pressure", 0.0)) >= 0.35
    viability_guard = policy.get("guard_reason") == "viability_pressure" or bool(policy.get("mvs_tension_active"))
    behavior_shift = _has_guard(retry_step)
    return round(_mean([1.0 if viability_rise else 0.0, 1.0 if viability_guard else 0.0, 1.0 if behavior_shift else 0.0]), 4)


def _score_corrective_trace_case(case_result: Dict[str, Any]) -> float:
    failure_step = _find_step(case_result, "tool_002")
    success_step = _find_step(case_result, "tool_004") or _find_step(case_result, "tool_005")
    success_trace = _canonical_trace(success_step)
    repair_closure = bool((success_trace.get("cycle_delta") or {}).get("repair_closure"))
    if not repair_closure:
        repair_closure = bool((success_step.get("state_snapshot") or {}).get("last_corrective_trace"))
    return round(
        _mean(
            [
                1.0 if _complete_corrective_trace(failure_step) else 0.0,
                1.0 if repair_closure else 0.0,
                1.0 if _trace_replayable(failure_step, require_corrective_fields=True) and _trace_replayable(success_step) else 0.0,
            ]
        ),
        4,
    )


def _score_variant(case_results: list[Dict[str, Any]]) -> VariantScores:
    family_groups: Dict[str, list[Dict[str, Any]]] = {
        "identity_continuity": [],
        "decision_conflict": [],
        "failure_repair_retry": [],
    }
    for case_result in case_results:
        family_groups.setdefault(str(case_result.get("family") or ""), []).append(case_result)

    target_scores = {
        "T1": round(_mean(_score_identity_case(case) for case in family_groups["identity_continuity"]), 4),
        "T2": round(_mean(_score_decision_case(case) for case in family_groups["decision_conflict"]), 4),
        "T3": round(_mean(_score_plasticity_case(case) for case in family_groups["failure_repair_retry"]), 4),
        "T4": round(_mean(_score_tension_case(case) for case in family_groups["failure_repair_retry"]), 4),
        "T5": round(_mean(_score_corrective_trace_case(case) for case in family_groups["failure_repair_retry"]), 4),
    }

    boundary_cases = family_groups["identity_continuity"] + family_groups["decision_conflict"]
    boundary_integrity = round(
        _mean(
            1.0
            if all(str((step.get("response_tendency") or {}).get("preferred_mode") or "") != "respond" for step in list(case.get("steps") or []))
            else 0.0
            for case in boundary_cases
        ),
        4,
    )
    repair_closure_capture = round(
        _mean(
            1.0 if bool((_canonical_trace(_find_step(case, "tool_004")).get("cycle_delta") or {}).get("repair_closure"))
            or bool((_canonical_trace(_find_step(case, "tool_005")).get("cycle_delta") or {}).get("repair_closure"))
            else 0.0
            for case in family_groups["failure_repair_retry"]
        ),
        4,
    )
    all_steps = [step for case in case_results for step in list(case.get("steps") or [])]
    trace_replayability = round(_mean(1.0 if _trace_replayable(step) else 0.0 for step in all_steps), 4)
    composite = round(_mean(target_scores.values()), 4)
    return VariantScores(
        target_scores=target_scores,
        composite=composite,
        boundary_integrity=boundary_integrity,
        repair_closure_capture=repair_closure_capture,
        trace_replayability=trace_replayability,
    )


def _baseline_b_scores() -> VariantScores:
    scores = {target: 0.0 for target in TARGET_THRESHOLDS}
    return VariantScores(
        target_scores=scores,
        composite=0.0,
        boundary_integrity=1.0,
        repair_closure_capture=0.0,
        trace_replayability=0.0,
    )


def _passes_frozen_gate(
    candidate: VariantScores,
    *,
    baseline_a: VariantScores,
    require_ablation_drops: Dict[str, float] | None = None,
) -> tuple[bool, Dict[str, float], float, list[str], Dict[str, str]]:
    target_deltas = {
        target: round(candidate.target_scores[target] - baseline_a.target_scores[target], 4)
        for target in TARGET_THRESHOLDS
    }
    composite_delta = round(candidate.composite - baseline_a.composite, 4)
    target_delta_rules: Dict[str, str] = {}
    target_delta_pass = True
    for target, delta in target_deltas.items():
        baseline_score = baseline_a.target_scores[target]
        if baseline_score >= SATURATED_BASELINE_THRESHOLD:
            target_delta_rules[target] = f"non_regression>={SATURATED_TARGET_REGRESSION_FLOOR}"
            if delta < SATURATED_TARGET_REGRESSION_FLOOR:
                target_delta_pass = False
        else:
            target_delta_rules[target] = f"delta>={NON_SATURATED_TARGET_DELTA_THRESHOLD}"
            if delta < NON_SATURATED_TARGET_DELTA_THRESHOLD:
                target_delta_pass = False
    candidate_pass = (
        all(candidate.target_scores[target] >= threshold for target, threshold in TARGET_THRESHOLDS.items())
        and candidate.composite >= COMPOSITE_THRESHOLD
        and composite_delta >= 0.10
        and target_delta_pass
        and candidate.boundary_integrity >= 1.0
        and candidate.repair_closure_capture >= 0.80
        and candidate.trace_replayability >= 0.90
    )
    weak_ablations: list[str] = []
    if require_ablation_drops is not None:
        weak_ablations = [name for name, drop in require_ablation_drops.items() if drop < 0.04]
        candidate_pass = candidate_pass and len(weak_ablations) < 2
    return candidate_pass, target_deltas, composite_delta, weak_ablations, target_delta_rules


def _selection_decision(
    candidate: VariantScores,
    baseline_a: VariantScores,
    ablations: Dict[str, VariantScores],
    challenger: VariantScores | None,
) -> Dict[str, Any]:
    ablation_drops = {
        "counterfactual": round(candidate.target_scores["T3"] - ablations["mvs_minus_counterfactual_writeback"].target_scores["T3"], 4),
        "viability": round(candidate.target_scores["T4"] - ablations["mvs_minus_viability_pressure"].target_scores["T4"], 4),
        "corrective_trace": round(candidate.target_scores["T5"] - ablations["mvs_minus_corrective_trace"].target_scores["T5"], 4),
        "boundary_confidence": round(candidate.target_scores["T2"] - ablations["mvs_minus_boundary_confidence"].target_scores["T2"], 4),
    }
    candidate_pass, target_deltas, composite_delta, weak_ablations, target_delta_rules = _passes_frozen_gate(
        candidate,
        baseline_a=baseline_a,
        require_ablation_drops=ablation_drops,
    )
    challenger_status = "not_run"
    challenger_pass = False
    challenger_target_deltas: Dict[str, float] = {}
    challenger_composite_delta = 0.0
    switch_advantage = False
    if challenger is not None:
        challenger_pass, challenger_target_deltas, challenger_composite_delta, _, challenger_target_delta_rules = _passes_frozen_gate(
            challenger,
            baseline_a=baseline_a,
        )
        if challenger_pass:
            challenger_status = "pass"
        else:
            challenger_status = "fail"
        switch_advantage = (
            challenger.composite - candidate.composite >= 0.04
            and _mean(
                [
                    challenger.target_scores["T2"] - candidate.target_scores["T2"],
                    challenger.target_scores["T3"] - candidate.target_scores["T3"],
                    challenger.target_scores["T4"] - candidate.target_scores["T4"],
                ]
            ) >= 0.05
        )
    if not candidate_pass and challenger_pass:
        decision = "switch_to_active_inference"
    elif not candidate_pass and challenger is not None:
        decision = "research_reframe_required"
    elif candidate_pass and switch_advantage:
        decision = "switch_to_active_inference"
    elif not candidate_pass:
        decision = "switch_to_active_inference"
    else:
        decision = "stay_on_mvs"
    return {
        "decision": decision,
        "candidate_pass": candidate_pass,
        "target_deltas_vs_baseline_a": target_deltas,
        "target_delta_rules": target_delta_rules,
        "composite_delta_vs_baseline_a": composite_delta,
        "ablation_drops": ablation_drops,
        "weak_ablations": weak_ablations,
        "challenger_status": challenger_status,
        "challenger_pass": challenger_pass,
        "challenger_target_deltas_vs_baseline_a": challenger_target_deltas,
        "challenger_target_delta_rules": challenger_target_delta_rules if challenger is not None else {},
        "challenger_composite_delta_vs_baseline_a": round(challenger_composite_delta, 4),
        "challenger_switch_advantage": switch_advantage,
    }


def _bridge_selection_decision(
    *,
    candidate: VariantScores,
    baseline_a: VariantScores,
) -> Dict[str, Any]:
    candidate_pass, target_deltas, composite_delta, _, target_delta_rules = _passes_frozen_gate(
        candidate,
        baseline_a=baseline_a,
        require_ablation_drops=None,
    )
    return {
        "decision": "bridge_pass" if candidate_pass else "bridge_fail",
        "candidate_pass": candidate_pass,
        "target_deltas_vs_baseline_a": target_deltas,
        "target_delta_rules": target_delta_rules,
        "composite_delta_vs_baseline_a": composite_delta,
        "ablation_drops": {},
        "weak_ablations": [],
        "challenger_status": "not_applicable",
        "challenger_pass": False,
        "challenger_target_deltas_vs_baseline_a": {},
        "challenger_target_delta_rules": {},
        "challenger_composite_delta_vs_baseline_a": 0.0,
        "challenger_switch_advantage": False,
        "bridge_mode": True,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    selection = payload["selection"]
    lines = [
        "# MVS Replay Validator Scored",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- selection_decision: `{selection['decision']}`",
        f"- candidate_pass: `{selection['candidate_pass']}`",
        "",
        "## Target Scores",
        "",
    ]
    for variant_id, scores in payload["variant_scores"].items():
        lines.append(
            f"- `{variant_id}`: composite=`{scores['composite']}` "
            f"T1=`{scores['target_scores']['T1']}` T2=`{scores['target_scores']['T2']}` "
            f"T3=`{scores['target_scores']['T3']}` T4=`{scores['target_scores']['T4']}` T5=`{scores['target_scores']['T5']}`"
        )
    lines.extend(
        [
            "",
            "## Selection",
            "",
            f"- target_deltas_vs_baseline_a: `{selection['target_deltas_vs_baseline_a']}`",
            f"- target_delta_rules: `{selection['target_delta_rules']}`",
            f"- composite_delta_vs_baseline_a: `{selection['composite_delta_vs_baseline_a']}`",
            f"- ablation_drops: `{selection['ablation_drops']}`",
            f"- weak_ablations: `{selection['weak_ablations']}`",
            f"- challenger_status: `{selection['challenger_status']}`",
            f"- challenger_pass: `{selection['challenger_pass']}`",
            f"- challenger_target_deltas_vs_baseline_a: `{selection['challenger_target_deltas_vs_baseline_a']}`",
            f"- challenger_target_delta_rules: `{selection['challenger_target_delta_rules']}`",
            f"- challenger_composite_delta_vs_baseline_a: `{selection['challenger_composite_delta_vs_baseline_a']}`",
            f"- challenger_switch_advantage: `{selection['challenger_switch_advantage']}`",
        ]
    )
    authority_drift = payload.get("authority_drift_audit")
    trace_contract = payload.get("trace_contract_check")
    if authority_drift or trace_contract:
        lines.extend(["", "## Bridge Checks", ""])
        if authority_drift:
            lines.append(f"- authority_drift_status: `{authority_drift.get('status', 'unknown')}`")
        if trace_contract:
            lines.append(f"- trace_contract_status: `{trace_contract.get('status', 'unknown')}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    report = _load_report(args.input)
    contract = dict(report.get("runner_contract") or {})
    results_by_variant = dict(report.get("results_by_variant") or {})

    variant_scores: Dict[str, VariantScores] = {}
    for variant_id, case_results in results_by_variant.items():
        variant_scores[variant_id] = _score_variant(list(case_results))
    variant_scores[contract["baseline_b_id"]] = _baseline_b_scores()

    challenger_id = contract.get("challenger_id")
    challenger = variant_scores.get(challenger_id) if challenger_id else None
    ablation_ids = list(contract.get("ablation_ids") or [])
    if ablation_ids:
        selection = _selection_decision(
            candidate=variant_scores[contract["candidate_id"]],
            baseline_a=variant_scores[contract["baseline_a_id"]],
            ablations={ablation_id: variant_scores[ablation_id] for ablation_id in ablation_ids},
            challenger=challenger,
        )
    else:
        selection = _bridge_selection_decision(
            candidate=variant_scores[contract["candidate_id"]],
            baseline_a=variant_scores[contract["baseline_a_id"]],
        )

    payload = {
        "schema_version": "mvs.replay_validator_scored.v1",
        "generated_at": _now_iso(),
        "input_report": str(args.input),
        "variant_scores": {variant_id: scores.to_dict() for variant_id, scores in variant_scores.items()},
        "selection": selection,
    }
    if report.get("authority_drift_audit") is not None:
        payload["authority_drift_audit"] = dict(report.get("authority_drift_audit") or {})
    if report.get("trace_contract_check") is not None:
        payload["trace_contract_check"] = dict(report.get("trace_contract_check") or {})
    _write_json(args.output_json, payload)
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")


if __name__ == "__main__":
    main()
