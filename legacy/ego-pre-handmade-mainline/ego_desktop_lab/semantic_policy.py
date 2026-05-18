from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.event_log import EvidenceRecord
from ego_desktop_lab.gate import GateDecision, evaluate_gate
from ego_desktop_lab.intention import Intention, select_intention
from ego_desktop_lab.learning import apply_pressure_bias
from ego_desktop_lab.policy import INTENTION_SPECS, calculate_pressure_priority
from ego_desktop_lab.reducer import AgentCycleResult, build_suggestion
from ego_desktop_lab.semantic_proposal import BINDING_BOUND, SemanticProposal
from ego_desktop_lab.tension import Tension


SEMANTIC_POLICY_CONFIDENCE_THRESHOLD = 0.60


@dataclass(frozen=True)
class SemanticPolicyOverlay:
    applied: bool
    accepted_failure_type: str | None
    related_goal_id: str | None
    binding_status: str | None
    target_affordance: str | None
    candidate_goals: tuple[str, ...]
    pressure_bias: dict[str, float]
    affordance_bias: dict[str, float]
    reason: str


@dataclass(frozen=True)
class CanonicalDecision:
    before_selected_intention: Intention | None
    after_selected_intention: Intention | None
    semantic_policy_overlay_applied: bool
    accepted_failure_type: str | None
    selected_goal_id: str | None
    selection_change_reason: str
    decision_source: str


@dataclass(frozen=True)
class SemanticPolicyCalibrationResult:
    overlay: SemanticPolicyOverlay
    before_pressure_map: dict[str, float]
    after_pressure_map: dict[str, float]
    before_selected_intention: Intention | None
    after_generated_intentions: tuple[Intention, ...]
    after_selected_intention: Intention | None
    gate_decision: GateDecision
    suggestion: str
    selection_change_reason: str
    canonical_decision: CanonicalDecision

    def to_evidence_fields(self) -> dict[str, object]:
        return {
            "canonical_decision": self.canonical_decision,
            "canonical_gate_decision": self.gate_decision,
            "accepted_failure_type": self.overlay.accepted_failure_type,
            "semantic_policy_overlay": self.overlay,
            "before_pressure_map": self.before_pressure_map,
            "after_pressure_map": self.after_pressure_map,
            "before_selected_intention": self.canonical_decision.before_selected_intention,
            "after_selected_intention": self.canonical_decision.after_selected_intention,
            "selection_change_reason": self.canonical_decision.selection_change_reason,
        }


def derive_semantic_policy_overlay(proposal: SemanticProposal | None) -> SemanticPolicyOverlay:
    if proposal is None:
        return _noop_overlay("no accepted semantic proposal")
    if proposal.binding_status != BINDING_BOUND or not proposal.related_goal_id:
        return _noop_overlay("proposal is pending goal binding", proposal)
    if proposal.candidate_failure_type == "ambiguous_concern":
        return _noop_overlay("ambiguous concern requires clarification", proposal)
    if proposal.confidence < SEMANTIC_POLICY_CONFIDENCE_THRESHOLD:
        return _noop_overlay("semantic proposal confidence below policy threshold", proposal)

    mapping = {
        "evidence_failure": (
            "verify",
            ("verify_before_claim",),
            {"uncertainty_precision": 0.30, "prediction_error": -0.08},
            {"verify": 0.42},
            "evidence failure calibrated toward verification before claims",
        ),
        "plan_failure": (
            "repair",
            ("repair_or_replan_goal",),
            {"viability_error": 0.20, "prediction_error": 0.35},
            {"repair": 0.45},
            "plan failure calibrated toward repair or replan",
        ),
        "execution_failure": (
            "execution_retry",
            ("retry_or_change_tool",),
            {"viability_error": 0.35, "prediction_error": 0.25},
            {"execution_retry": 0.65},
            "execution failure calibrated toward bounded retry or tool change",
        ),
        "permission_failure": (
            "permission_gate",
            ("ask_permission_or_defer",),
            {"boundary_error": 0.45, "viability_error": 0.10},
            {"permission_gate": 0.65},
            "permission failure calibrated toward ask/defer gate",
        ),
        "destructive_action_request": (
            "destructive_action",
            ("block_destructive_action",),
            {"boundary_error": 0.70, "viability_error": 0.20},
            {"destructive_action": 0.80},
            "destructive action request calibrated toward a blocked safety boundary",
        ),
        "external_send_request": (
            "external_send",
            ("block_external_send",),
            {"boundary_error": 0.68, "viability_error": 0.18},
            {"external_send": 0.78},
            "external send request calibrated toward a blocked safety boundary",
        ),
        "claim_boundary_query": (
            "verify",
            ("verify_before_claim",),
            {"uncertainty_precision": 0.35, "boundary_error": 0.25},
            {"verify": 0.40},
            "consciousness claim query calibrated toward claim ceiling and evidence boundary",
        ),
        "goal_definition_failure": (
            "goal_definition",
            ("reframe_or_split_goal", "split_goal_or_redefine_success_criteria"),
            {"commitment_error": 0.30, "prediction_error": 0.15, "uncertainty_precision": 0.20},
            {"goal_definition": 0.65},
            "goal definition failure calibrated toward reframe or split",
        ),
    }
    if proposal.candidate_failure_type not in mapping:
        return _noop_overlay(f"unsupported semantic failure type: {proposal.candidate_failure_type}", proposal)
    target_affordance, candidate_goals, pressure_bias, affordance_bias, reason = mapping[proposal.candidate_failure_type]
    return SemanticPolicyOverlay(
        applied=True,
        accepted_failure_type=proposal.candidate_failure_type,
        related_goal_id=proposal.related_goal_id,
        binding_status=proposal.binding_status,
        target_affordance=target_affordance,
        candidate_goals=candidate_goals,
        pressure_bias={key: round(float(value), 6) for key, value in pressure_bias.items()},
        affordance_bias={key: round(float(value), 6) for key, value in affordance_bias.items()},
        reason=reason,
    )


def run_semantic_policy_calibration_cycle(
    before_result: AgentCycleResult,
    after_base_result: AgentCycleResult | None,
    proposal: SemanticProposal | None,
) -> SemanticPolicyCalibrationResult:
    overlay = derive_semantic_policy_overlay(proposal)
    before_map = dict(before_result.affordance_pressure)
    base_result = after_base_result if after_base_result is not None else before_result
    if not overlay.applied:
        selected = before_result.selected_intention
        gate_decision = before_result.gate_decision
        suggestion = before_result.suggestion
        reason = f"semantic policy overlay not applied: {overlay.reason}"
        canonical_decision = _build_canonical_decision(
            overlay,
            before_result.selected_intention,
            selected,
            reason,
        )
        return SemanticPolicyCalibrationResult(
            overlay=overlay,
            before_pressure_map=before_map,
            after_pressure_map=before_map,
            before_selected_intention=before_result.selected_intention,
            after_generated_intentions=before_result.generated_intentions,
            after_selected_intention=selected,
            gate_decision=gate_decision,
            suggestion=suggestion,
            selection_change_reason=reason,
            canonical_decision=canonical_decision,
        )

    calibrated_pressure = apply_pressure_bias(base_result.motivation_pressure, overlay.pressure_bias)
    after_map = _apply_affordance_bias(calibrated_pressure.affordance_map(), overlay.affordance_bias)
    policy_intentions = tuple(
        _build_policy_intention(index, goal, before_result, base_result, after_map, overlay)
        for index, goal in enumerate(overlay.candidate_goals, start=1)
    )
    generated = (*base_result.generated_intentions, *policy_intentions)
    selected = select_intention(generated)
    if selected is None:
        gate_decision = before_result.gate_decision
        suggestion = before_result.suggestion
    else:
        gate_decision = evaluate_gate(selected.proposed_action)
        suggestion = build_suggestion(selected, gate_decision, build_suggestion_state(before_result))
    reason = _selection_reason(before_result.selected_intention, selected, overlay)
    canonical_decision = _build_canonical_decision(
        overlay,
        before_result.selected_intention,
        selected,
        reason,
    )
    return SemanticPolicyCalibrationResult(
        overlay=overlay,
        before_pressure_map=before_map,
        after_pressure_map=after_map,
        before_selected_intention=before_result.selected_intention,
        after_generated_intentions=generated,
        after_selected_intention=selected,
        gate_decision=gate_decision,
        suggestion=suggestion,
        selection_change_reason=reason,
        canonical_decision=canonical_decision,
    )


def build_semantic_policy_evidence_record(
    result: SemanticPolicyCalibrationResult,
    base_record: EvidenceRecord,
) -> EvidenceRecord:
    fields = result.to_evidence_fields()
    return EvidenceRecord(
        **{
            **base_record.to_dict(),
            "accepted_failure_type": fields["accepted_failure_type"],
            "canonical_decision": fields["canonical_decision"],
            "canonical_gate_decision": fields["canonical_gate_decision"],
            "semantic_policy_overlay": fields["semantic_policy_overlay"],
            "before_pressure_map": fields["before_pressure_map"],
            "after_pressure_map": fields["after_pressure_map"],
            "before_selected_intention": fields["before_selected_intention"],
            "after_selected_intention": fields["after_selected_intention"],
            "selection_change_reason": fields["selection_change_reason"],
        }
    )


def build_suggestion_state(result: AgentCycleResult):
    from ego_desktop_lab.subject_state import SubjectState

    summary = result.old_state_summary
    return SubjectState(
        agent_id=str(summary["agent_id"]),
        core_commitments=tuple(str(item) for item in summary["core_commitments"]),
        uncertainty=float(summary["uncertainty"]),
        integrity=float(summary["integrity"]),
        goal_pressure=float(summary["goal_pressure"]),
        risk_sensitivity=float(summary["risk_sensitivity"]),
        unfinished_goals=tuple(summary["unfinished_goals"]),  # type: ignore[arg-type]
        recent_failures=(),
        identity_conflict=bool(summary["identity_conflict"]),
    )


def _noop_overlay(reason: str, proposal: SemanticProposal | None = None) -> SemanticPolicyOverlay:
    return SemanticPolicyOverlay(
        applied=False,
        accepted_failure_type=proposal.candidate_failure_type if proposal else None,
        related_goal_id=proposal.related_goal_id if proposal else None,
        binding_status=proposal.binding_status if proposal else None,
        target_affordance=None,
        candidate_goals=(),
        pressure_bias={},
        affordance_bias={},
        reason=reason,
    )


def _apply_affordance_bias(base_map: dict[str, float], bias: dict[str, float]) -> dict[str, float]:
    keys = sorted(set(base_map).union(bias))
    return {key: clamp01(base_map.get(key, 0.0) + bias.get(key, 0.0)) for key in keys}


def _build_policy_intention(
    index: int,
    goal: str,
    before_result: AgentCycleResult,
    base_result: AgentCycleResult,
    after_pressure_map: dict[str, float],
    overlay: SemanticPolicyOverlay,
) -> Intention:
    spec = INTENTION_SPECS[goal]
    tension = _select_tension(before_result, base_result, overlay.related_goal_id)
    affordance = str(spec["affordance"])
    priority = calculate_pressure_priority(
        affordance_pressure=after_pressure_map[affordance],
        tension_severity=tension.severity,
        expected_value=float(spec["expected_value"]),
        risk=float(spec["risk"]),
        cost=float(spec["cost"]),
    )
    return Intention(
        id=f"intention:semantic_policy:{overlay.accepted_failure_type}:{index:03d}:{goal}",
        goal=goal,
        reason=str(spec["reason"]),
        source_tension=tension,
        priority=priority,
        risk=float(spec["risk"]),
        cost=float(spec["cost"]),
        proposed_action=str(spec["proposed_action"]),
        affordance=affordance,
        goal_id=tension.goal_id or overlay.related_goal_id,
        goal_description=tension.goal_description,
    )


def _select_tension(
    before_result: AgentCycleResult,
    base_result: AgentCycleResult,
    related_goal_id: str | None,
) -> Tension:
    for tension in (*base_result.tensions, *before_result.tensions):
        if related_goal_id and tension.goal_id == related_goal_id:
            return tension
    if before_result.selected_intention is not None:
        return before_result.selected_intention.source_tension
    return Tension(type="semantic_policy", severity=0.80, source="semantic_policy")


def _selection_reason(
    before: Intention | None,
    after: Intention | None,
    overlay: SemanticPolicyOverlay,
) -> str:
    before_goal = before.goal if before else None
    after_goal = after.goal if after else None
    if before_goal == after_goal:
        return f"{overlay.accepted_failure_type} retained {after_goal}: {overlay.reason}"
    return f"{overlay.accepted_failure_type} changed selection from {before_goal} to {after_goal}: {overlay.reason}"


def _build_canonical_decision(
    overlay: SemanticPolicyOverlay,
    before: Intention | None,
    after: Intention | None,
    selection_change_reason: str,
) -> CanonicalDecision:
    return CanonicalDecision(
        before_selected_intention=before,
        after_selected_intention=after,
        semantic_policy_overlay_applied=overlay.applied,
        accepted_failure_type=overlay.accepted_failure_type,
        selected_goal_id=_selected_goal_id(before, after, overlay),
        selection_change_reason=selection_change_reason,
        decision_source="semantic_policy_calibration" if overlay.applied else "semantic_policy_noop",
    )


def _selected_goal_id(
    before: Intention | None,
    after: Intention | None,
    overlay: SemanticPolicyOverlay,
) -> str | None:
    if after is not None and after.goal_id:
        return after.goal_id
    if overlay.related_goal_id:
        return overlay.related_goal_id
    if before is not None and before.goal_id:
        return before.goal_id
    return None
