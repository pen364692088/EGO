from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ego_desktop_lab.appraisal import AppraisalResult, appraise
from ego_desktop_lab.belief_state import BeliefState, build_demo_belief_state
from ego_desktop_lab.event_log import EvidenceRecord, append_evidence_record
from ego_desktop_lab.gate import GateDecision, evaluate_gate
from ego_desktop_lab.intention import Intention, generate_intentions, select_intention
from ego_desktop_lab.motivation import (
    DEFAULT_MOTIVATION,
    MotivationState,
    motivation_diff,
    update_motivation,
)
from ego_desktop_lab.learning import apply_pressure_bias
from ego_desktop_lab.pressure import MotivationPressure, derive_motivation_pressure
from ego_desktop_lab.subject_state import SubjectState
from ego_desktop_lab.tension import Tension, detect_tensions


@dataclass(frozen=True)
class AgentCycleResult:
    old_state_summary: dict[str, object]
    belief_state: BeliefState
    tensions: tuple[Tension, ...]
    appraisal: AppraisalResult
    motivation_before: MotivationState
    motivation_after: MotivationState
    motivation_diff: dict[str, dict[str, float]]
    motivation_pressure: MotivationPressure
    affordance_pressure: dict[str, float]
    generated_intentions: tuple[Intention, ...]
    selected_intention: Intention | None
    gate_decision: GateDecision
    suggestion: str
    evidence_record: EvidenceRecord
    evidence_log_path: Path


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_agent_cycle(
    state: SubjectState,
    *,
    evidence_log_path: Path,
    timestamp: str | None = None,
    belief_state: BeliefState | None = None,
    motivation_state: MotivationState = DEFAULT_MOTIVATION,
    pressure_bias: dict[str, float] | None = None,
    append_evidence: bool = True,
) -> AgentCycleResult:
    record_timestamp = timestamp or utc_timestamp()
    active_belief = belief_state or build_demo_belief_state()
    old_state_summary = state.summary()
    tensions = detect_tensions(state)
    appraisal = appraise(state, active_belief)
    motivation_after = update_motivation(motivation_state, appraisal)
    diff = motivation_diff(motivation_state, motivation_after)
    motivation_pressure = apply_pressure_bias(
        derive_motivation_pressure(state, active_belief, appraisal),
        pressure_bias,
    )
    affordance_pressure = motivation_pressure.affordance_map()
    intentions = generate_intentions(tensions, motivation_pressure)
    selected_intention = select_intention(intentions)

    if selected_intention is None:
        gate_decision = GateDecision(
            status="block",
            reason="No state-derived intention was generated.",
            allowed_as="none",
        )
        suggestion = "No suggestion: no state-derived tension crossed the v0 threshold."
        event_id = f"event:none:{record_timestamp}"
    else:
        gate_decision = evaluate_gate(selected_intention.proposed_action)
        suggestion = build_suggestion(selected_intention, gate_decision, state)
        event_id = f"event:{selected_intention.id}:{record_timestamp}"

    evidence_record = EvidenceRecord(
        event_id=event_id,
        old_state_summary=old_state_summary,
        belief_state=active_belief,
        tensions=tensions,
        appraisal=appraisal,
        motivation_before=motivation_state,
        motivation_after=motivation_after,
        motivation_diff=diff,
        motivation_pressure=motivation_pressure,
        affordance_pressure=affordance_pressure,
        generated_intentions=intentions,
        selected_intention=selected_intention,
        gate_decision=gate_decision,
        suggestion=suggestion,
        timestamp=record_timestamp,
    )
    if append_evidence:
        append_evidence_record(evidence_log_path, evidence_record)

    return AgentCycleResult(
        old_state_summary=old_state_summary,
        belief_state=active_belief,
        tensions=tensions,
        appraisal=appraisal,
        motivation_before=motivation_state,
        motivation_after=motivation_after,
        motivation_diff=diff,
        motivation_pressure=motivation_pressure,
        affordance_pressure=affordance_pressure,
        generated_intentions=intentions,
        selected_intention=selected_intention,
        gate_decision=gate_decision,
        suggestion=suggestion,
        evidence_record=evidence_record,
        evidence_log_path=evidence_log_path,
    )


def build_suggestion(
    intention: Intention,
    gate_decision: GateDecision,
    state: SubjectState,
) -> str:
    if gate_decision.status == "block":
        return (
            f"No suggestion: proposed action '{intention.proposed_action}' was blocked "
            f"because {gate_decision.reason}"
        )

    prefix = "Suggestion" if gate_decision.status == "allow" else "Approval required"
    if intention.goal == "continue_or_verify_unfinished_goal":
        goal = intention.goal_description or (
            state.unfinished_goals[0].description if state.unfinished_goals else "the unfinished goal"
        )
        return f"{prefix}: continue or verify unfinished goal '{goal}'."
    if intention.goal == "verify_before_claim":
        return f"{prefix}: verify uncertainty-sensitive claims before presenting them."
    if intention.goal == "repair_or_replan_goal":
        return f"{prefix}: repair or replan the goal before continuing."
    if intention.goal == "preserve_identity_boundary":
        return f"{prefix}: preserve identity commitments and escalate the conflict for review."
    if intention.goal == "reframe_or_split_goal":
        return f"{prefix}: reframe the goal or split it before continuing the loop."
    if intention.goal == "split_goal_or_redefine_success_criteria":
        return f"{prefix}: split the goal or redefine success criteria before another repair."
    if intention.goal == "ask_permission_or_defer":
        return f"{prefix}: ask for permission or defer instead of acting autonomously."
    if intention.goal == "retry_or_change_tool":
        return f"{prefix}: retry with a bounded change or propose a different tool path."
    return f"{prefix}: review state-derived intention '{intention.goal}'."
