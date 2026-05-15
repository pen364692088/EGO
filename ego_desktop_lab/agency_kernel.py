from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from ego_desktop_lab.affective_drive_loop import (
    AffectiveDriveState,
    derive_affective_drive_state,
)
from ego_desktop_lab.behavior_options import (
    BehaviorOptionRegistration,
    DEFAULT_BEHAVIOR_OPTION_REGISTRY,
    build_selection_restriction_diagnostic,
    build_behavior_options,
    select_behavior_option,
)
from ego_desktop_lab.agency_contracts import (
    AgencyEvent,
    PerceptionFrame,
    build_behavior_plan,
    build_fixture_agency_event,
    derive_perception_frame,
)
from ego_desktop_lab.belief_state import BeliefState, build_demo_belief_state
from ego_desktop_lab.experience_memory import (
    CLAIM_CEILING as EXPERIENCE_MEMORY_CLAIM_CEILING,
    ExperienceBias,
    ExperienceCard,
    build_current_experience_context,
    derive_experience_bias,
)
from ego_desktop_lab.gate import GateDecision
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.learning import (
    LearningUpdate,
    apply_learning_to_belief,
    apply_learning_to_state,
    derive_learning_update,
    merge_pressure_bias,
    run_learning_cycle,
)
from ego_desktop_lab.outcome import OutcomeRecord, strategy_id_for_goal
from ego_desktop_lab.policy import GATE_ACTION_STATUS, INTENTION_SPECS
from ego_desktop_lab.reducer import AgentCycleResult, run_agent_cycle
from ego_desktop_lab.strategy_memory import (
    StrategyMemory,
    StrategyMemoryBank,
    default_strategy_memory,
    update_strategy_memory,
)
from ego_desktop_lab.subject_state import SubjectState


CLAIM_CEILING = (
    "lab-only viability-to-proposal coupling proof; no consciousness, no alive status, "
    "no live autonomy, no runtime efficacy, no user benefit, and no external action executed"
)

NO_WRITE_EVIDENCE_PATH = Path("/tmp/ego_desktop_lab_v7_agency_kernel_no_write.jsonl")


@dataclass(frozen=True)
class SelfMaintainingAgencyCycleResult:
    lab_spine_summary: dict[str, object]
    agency_event_snapshot: dict[str, object]
    perception_frame_snapshot: dict[str, object]
    boundary_summary: dict[str, object]
    viability_snapshot: dict[str, object]
    affective_drive_snapshot: dict[str, object]
    predictions_by_affordance: dict[str, dict[str, object]]
    behavior_options: tuple[dict[str, object], ...]
    candidate_options: tuple[dict[str, object], ...]
    selected_behavior_option: dict[str, object] | None
    selection_restriction: dict[str, object]
    selected_intention: dict[str, object] | None
    behavior_plan: dict[str, object]
    gate_decision: dict[str, object]
    experience_memory_snapshot: dict[str, object]
    plasticity_update: dict[str, object] | None
    next_cycle_delta: dict[str, object]
    no_action_executed: bool
    claim_ceiling: str
    evidence_log_path: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "lab_spine_summary": self.lab_spine_summary,
            "agency_event_snapshot": self.agency_event_snapshot,
            "perception_frame_snapshot": self.perception_frame_snapshot,
            "boundary_summary": self.boundary_summary,
            "viability_snapshot": self.viability_snapshot,
            "affective_drive_snapshot": self.affective_drive_snapshot,
            "predictions_by_affordance": self.predictions_by_affordance,
            "behavior_options": list(self.behavior_options),
            "candidate_options": list(self.candidate_options),
            "selected_behavior_option": self.selected_behavior_option,
            "selection_restriction": self.selection_restriction,
            "selected_intention": self.selected_intention,
            "behavior_plan": self.behavior_plan,
            "gate_decision": self.gate_decision,
            "experience_memory_snapshot": self.experience_memory_snapshot,
            "plasticity_update": self.plasticity_update,
            "next_cycle_delta": self.next_cycle_delta,
            "no_action_executed": self.no_action_executed,
            "claim_ceiling": self.claim_ceiling,
            "evidence_log_path": self.evidence_log_path,
        }


@dataclass(frozen=True)
class _PlasticityProjection:
    before_result: AgentCycleResult
    next_result: AgentCycleResult
    learning_update: LearningUpdate
    strategy_memory_before: StrategyMemoryBank
    strategy_memory_after: StrategyMemoryBank
    evidence_log_path: Path | None


def run_self_maintaining_agency_cycle(
    state: SubjectState,
    belief_state: BeliefState | None = None,
    *,
    outcome: OutcomeRecord | None = None,
    strategy_memory_bank: StrategyMemoryBank | None = None,
    evidence_log_path: Path | None = None,
    timestamp: str | None = None,
    initial_pressure_bias: dict[str, float] | None = None,
    affective_drive_state: AffectiveDriveState | None = None,
    experience_cards: tuple[ExperienceCard, ...] | None = None,
    agency_event: AgencyEvent | None = None,
    perception_frame: PerceptionFrame | None = None,
    behavior_option_registry: Mapping[
        str,
        BehaviorOptionRegistration,
    ] = DEFAULT_BEHAVIOR_OPTION_REGISTRY,
) -> SelfMaintainingAgencyCycleResult:
    """Run the v7 lab-only self-maintaining agency facade.

    This is a thin observation facade over the existing deterministic desktop-lab
    kernel. It is not a runtime owner, tool executor, desktop controller, or
    formal EGO mainline authority.
    """

    active_belief = belief_state or build_demo_belief_state()
    active_event = agency_event or build_fixture_agency_event(
        agent_id=state.agent_id,
        goals=tuple(item.description for item in state.unfinished_goals),
    )
    active_perception = perception_frame or derive_perception_frame(active_event)
    experience_context = build_current_experience_context(state, active_belief)
    experience_bias = derive_experience_bias(tuple(experience_cards or ()), experience_context)
    affective_bias = affective_drive_state.pressure_bias_delta() if affective_drive_state else None
    effective_pressure_bias = (
        merge_pressure_bias(initial_pressure_bias, affective_bias)
        if affective_bias is not None
        else initial_pressure_bias
    )
    effective_pressure_bias = merge_pressure_bias(
        effective_pressure_bias,
        experience_bias.pressure_bias_delta,
    )
    if outcome is None:
        before_result = run_agent_cycle(
            state,
            evidence_log_path=evidence_log_path or NO_WRITE_EVIDENCE_PATH,
            timestamp=timestamp,
            belief_state=active_belief,
            pressure_bias=effective_pressure_bias,
            append_evidence=False,
        )
        next_result = before_result
        plasticity = None
    else:
        plasticity = _run_plasticity_projection(
            state,
            active_belief,
            outcome,
            strategy_memory_bank=strategy_memory_bank,
            evidence_log_path=evidence_log_path,
            timestamp=timestamp,
            initial_pressure_bias=effective_pressure_bias,
        )
        before_result = plasticity.before_result
        next_result = plasticity.next_result

    active_result = next_result
    active_drive = affective_drive_state or derive_affective_drive_state(before_result.motivation_pressure)
    predictions = _build_predictions_by_affordance(
        active_result,
        plasticity.strategy_memory_after if plasticity is not None else strategy_memory_bank,
        experience_bias,
    )
    behavior_options = build_behavior_options(
        active_result.generated_intentions,
        predictions,
        registry=behavior_option_registry,
    )
    selected_behavior = select_behavior_option(behavior_options, active_result.selected_intention)
    selection_restriction = build_selection_restriction_diagnostic(
        selected_intention=active_result.selected_intention,
        selected_behavior_option=selected_behavior,
        generated_intentions=active_result.generated_intentions,
        behavior_options=behavior_options,
        registry=behavior_option_registry,
    )
    selected_behavior_dict = selected_behavior.to_dict() if selected_behavior is not None else None
    gate_decision = _gate_to_dict(active_result.gate_decision)
    behavior_plan = build_behavior_plan(
        selected_behavior_dict,
        selection_restriction=selection_restriction,
        gate_decision=gate_decision,
    )
    return SelfMaintainingAgencyCycleResult(
        lab_spine_summary=_build_lab_spine_summary(),
        agency_event_snapshot=active_event.to_dict(),
        perception_frame_snapshot=active_perception.to_dict(),
        boundary_summary=_build_boundary_summary(state),
        viability_snapshot=_build_viability_snapshot(before_result, next_result),
        affective_drive_snapshot=_build_affective_drive_snapshot(
            active_drive,
            affective_drive_state is not None,
        ),
        predictions_by_affordance=predictions,
        behavior_options=tuple(option.to_dict() for option in behavior_options),
        candidate_options=_build_candidate_options(active_result),
        selected_behavior_option=selected_behavior_dict,
        selection_restriction=selection_restriction,
        selected_intention=_intention_to_dict(active_result.selected_intention),
        behavior_plan=behavior_plan.to_dict(),
        gate_decision=gate_decision,
        experience_memory_snapshot=_build_experience_memory_snapshot(
            experience_context,
            experience_bias,
            tuple(experience_cards or ()),
        ),
        plasticity_update=(
            _learning_update_to_dict(plasticity.learning_update) if plasticity is not None else None
        ),
        next_cycle_delta=_build_next_cycle_delta(before_result, next_result, plasticity),
        no_action_executed=True,
        claim_ceiling=CLAIM_CEILING,
        evidence_log_path=str(plasticity.evidence_log_path) if plasticity and plasticity.evidence_log_path else None,
    )


def _build_lab_spine_summary() -> dict[str, object]:
    return {
        "active_innovation_spine": "ego_desktop_lab",
        "formal_program_state_override": False,
        "formal_evidence_ledger_write": False,
        "runtime_reply_influence": False,
        "openemotion_state_mutation": False,
        "old_runtime_role": "reference_and_future_integration_candidate",
        "future_runtime_connection": "shadow_event_tap_only",
    }


def _run_plasticity_projection(
    state: SubjectState,
    belief_state: BeliefState,
    outcome: OutcomeRecord,
    *,
    strategy_memory_bank: StrategyMemoryBank | None,
    evidence_log_path: Path | None,
    timestamp: str | None,
    initial_pressure_bias: dict[str, float] | None,
) -> _PlasticityProjection:
    if evidence_log_path is not None:
        result = run_learning_cycle(
            state,
            belief_state,
            outcome,
            evidence_log_path=evidence_log_path,
            timestamp=timestamp or "2026-05-14T00:00:00+00:00",
            strategy_memory_bank=strategy_memory_bank,
            initial_pressure_bias=initial_pressure_bias,
        )
        return _PlasticityProjection(
            before_result=result.before_result,
            next_result=result.next_result,
            learning_update=result.learning_update,
            strategy_memory_before=result.strategy_memory_before,
            strategy_memory_after=result.strategy_memory_after,
            evidence_log_path=result.evidence_log_path,
        )

    record_timestamp = timestamp or "2026-05-14T00:00:00+00:00"
    before_result = run_agent_cycle(
        state,
        evidence_log_path=NO_WRITE_EVIDENCE_PATH,
        timestamp=record_timestamp,
        belief_state=belief_state,
        pressure_bias=initial_pressure_bias,
        append_evidence=False,
    )
    if before_result.selected_intention is None:
        raise ValueError("agency cycle requires a previous selected intention when outcome is provided")
    if outcome.selected_intention_id != before_result.selected_intention.id:
        raise ValueError("outcome selected_intention_id does not match the previous selected intention")
    if outcome.selected_plan_id != before_result.selected_intention.goal:
        raise ValueError("outcome selected_plan_id does not match the previous selected intention goal")

    learning_update = derive_learning_update(outcome)
    strategy_id = strategy_id_for_goal(outcome.selected_plan_id)
    bank = dict(strategy_memory_bank or {})
    memory_before = {**bank, strategy_id: bank.get(strategy_id, default_strategy_memory(strategy_id))}
    memory_after = update_strategy_memory(
        memory_before,
        outcome,
        record_timestamp,
        feedback_conflict=learning_update.feedback_conflict,
    )
    updated_state = apply_learning_to_state(state, outcome, learning_update)
    updated_belief = apply_learning_to_belief(belief_state, outcome, learning_update)
    next_result = run_agent_cycle(
        updated_state,
        evidence_log_path=NO_WRITE_EVIDENCE_PATH,
        timestamp=record_timestamp,
        belief_state=updated_belief,
        pressure_bias=merge_pressure_bias(initial_pressure_bias, learning_update.pressure_bias_delta),
        append_evidence=False,
    )
    return _PlasticityProjection(
        before_result=before_result,
        next_result=next_result,
        learning_update=learning_update,
        strategy_memory_before=memory_before,
        strategy_memory_after=memory_after,
        evidence_log_path=None,
    )


def _build_boundary_summary(state: SubjectState) -> dict[str, object]:
    return {
        "agent_id": state.agent_id,
        "owned_memory": "lab_belief_state_and_strategy_memory_only",
        "owned_goals": [item.description for item in state.unfinished_goals],
        "owned_commitments": list(state.core_commitments),
        "permission_status_by_action": dict(GATE_ACTION_STATUS),
        "protected_commitments": [
            "no_runtime_authority",
            "proposal_only",
            "no_file_write_delete_or_external_send",
            "no_consciousness_or_alive_claim",
        ],
    }


def _build_affective_drive_snapshot(
    drive_state: AffectiveDriveState,
    applied_to_pressure: bool,
) -> dict[str, object]:
    return {
        "state": drive_state.to_dict(),
        "pressure_bias_delta": drive_state.pressure_bias_delta() if applied_to_pressure else {},
        "applied_to_pressure": applied_to_pressure,
        "source": "ego_desktop_lab.affective_drive_loop.AffectiveDriveState",
        "claim": "bounded viability dynamics, not persona text or runtime authority",
    }


def _build_viability_snapshot(
    before_result: AgentCycleResult,
    next_result: AgentCycleResult,
) -> dict[str, object]:
    before = _dataclass_float_dict(before_result.motivation_pressure)
    after = _dataclass_float_dict(next_result.motivation_pressure)
    return {
        "before": before,
        "after": after,
        "delta": _delta(before, after),
        "source": "ego_desktop_lab.pressure.MotivationPressure",
    }


def _build_predictions_by_affordance(
    result: AgentCycleResult,
    strategy_memory_bank: StrategyMemoryBank | None,
    experience_bias: ExperienceBias | None = None,
) -> dict[str, dict[str, object]]:
    predictions: dict[str, dict[str, object]] = {}
    for intention in result.generated_intentions:
        spec = INTENTION_SPECS[intention.goal]
        strategy_confidence = _strategy_confidence_for_intention(
            strategy_memory_bank,
            intention,
            experience_bias,
        )
        pressure = result.affordance_pressure[intention.affordance]
        expected_value = float(spec["expected_value"])
        risk = float(spec["risk"])
        cost = float(spec["cost"])
        expected_viability_improvement = round(
            (pressure * expected_value * strategy_confidence) - risk - cost,
            6,
        )
        existing = predictions.get(intention.affordance)
        candidate = {
            "goal": intention.goal,
            "pressure": pressure,
            "expected_value": expected_value,
            "risk": risk,
            "cost": cost,
            "strategy_confidence": strategy_confidence,
            "experience_confidence_delta": _experience_confidence_delta_for_intention(
                intention,
                experience_bias,
            ),
            "expected_viability_improvement": expected_viability_improvement,
        }
        if existing is None or expected_viability_improvement > float(
            existing["expected_viability_improvement"]
        ):
            predictions[intention.affordance] = candidate
    return predictions


def _build_candidate_options(result: AgentCycleResult) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "rank": index,
            "id": intention.id,
            "goal": intention.goal,
            "affordance": intention.affordance,
            "priority": intention.priority,
            "risk": intention.risk,
            "cost": intention.cost,
            "proposed_action": intention.proposed_action,
            "gate_status": GATE_ACTION_STATUS[intention.proposed_action],
            "no_action_executed": True,
        }
        for index, intention in enumerate(
            sorted(result.generated_intentions, key=lambda item: (-item.priority, item.id)),
            start=1,
        )
    )


def _build_experience_memory_snapshot(
    experience_context: object,
    experience_bias: ExperienceBias,
    experience_cards: tuple[ExperienceCard, ...],
) -> dict[str, object]:
    return {
        "experience_applied": bool(experience_bias.applied_card_ids),
        "context": (
            experience_context.to_dict()
            if hasattr(experience_context, "to_dict")
            else dict(experience_context)  # type: ignore[arg-type]
        ),
        "card_count": len(experience_cards),
        "applied_card_ids": list(experience_bias.applied_card_ids),
        "ignored_card_ids": list(experience_bias.ignored_card_ids),
        "needs_review_card_ids": list(experience_bias.needs_review_card_ids),
        "effective_strength_by_card": dict(experience_bias.effective_strength_by_card),
        "pressure_bias_delta": dict(experience_bias.pressure_bias_delta),
        "strategy_confidence_delta_by_strategy": dict(
            experience_bias.strategy_confidence_delta_by_strategy
        ),
        "claim_ceiling": EXPERIENCE_MEMORY_CLAIM_CEILING,
    }


def _build_next_cycle_delta(
    before_result: AgentCycleResult,
    next_result: AgentCycleResult,
    plasticity: _PlasticityProjection | None,
) -> dict[str, object]:
    before_selected = before_result.selected_intention.goal if before_result.selected_intention else None
    after_selected = next_result.selected_intention.goal if next_result.selected_intention else None
    before_priorities = _priority_by_goal(before_result)
    after_priorities = _priority_by_goal(next_result)
    before_ranks = _rank_by_goal(before_result)
    after_ranks = _rank_by_goal(next_result)
    pressure_transition = _transition_by_key(
        before_result.affordance_pressure,
        next_result.affordance_pressure,
    )
    ranking_transition = _ranking_transition_by_goal(
        before_priorities,
        after_priorities,
        before_ranks,
        after_ranks,
    )
    return {
        "selected_intention_changed": before_selected != after_selected,
        "before_selected_goal": before_selected,
        "after_selected_goal": after_selected,
        "selected_transition": {
            "before_selected_goal": before_selected,
            "after_selected_goal": after_selected,
            "selected_intention_changed": before_selected != after_selected,
        },
        "pressure_transition": pressure_transition,
        "affordance_pressure_delta": _delta(
            before_result.affordance_pressure,
            next_result.affordance_pressure,
        ),
        "ranking_transition_by_goal": ranking_transition,
        "priority_delta_by_goal": {
            goal: round(after_priorities.get(goal, -999.0) - before_priorities.get(goal, -999.0), 6)
            for goal in sorted(set(before_priorities).union(after_priorities))
        },
        "rank_delta_by_goal": {
            goal: after_ranks.get(goal, 999) - before_ranks.get(goal, 999)
            for goal in sorted(set(before_ranks).union(after_ranks))
        },
        "plasticity_applied": plasticity is not None,
    }


def _transition_by_key(
    before: Mapping[str, float],
    after: Mapping[str, float],
) -> dict[str, dict[str, float]]:
    return {
        key: {
            "before": round(float(before.get(key, 0.0)), 6),
            "after": round(float(after.get(key, 0.0)), 6),
            "delta": round(float(after.get(key, 0.0)) - float(before.get(key, 0.0)), 6),
        }
        for key in sorted(set(before).union(after))
    }


def _ranking_transition_by_goal(
    before_priorities: Mapping[str, float],
    after_priorities: Mapping[str, float],
    before_ranks: Mapping[str, int],
    after_ranks: Mapping[str, int],
) -> dict[str, dict[str, object]]:
    transitions: dict[str, dict[str, object]] = {}
    for goal in sorted(set(before_priorities).union(after_priorities).union(before_ranks).union(after_ranks)):
        before_rank = before_ranks.get(goal)
        after_rank = after_ranks.get(goal)
        before_priority = before_priorities.get(goal)
        after_priority = after_priorities.get(goal)
        entered_ranking = before_rank is None and after_rank is not None
        left_ranking = before_rank is not None and after_rank is None
        rank_delta = after_rank - before_rank if before_rank is not None and after_rank is not None else None
        priority_delta = (
            round(after_priority - before_priority, 6)
            if before_priority is not None and after_priority is not None
            else None
        )
        transitions[goal] = {
            "before_rank": before_rank,
            "after_rank": after_rank,
            "rank_delta": rank_delta,
            "before_priority": round(float(before_priority), 6) if before_priority is not None else None,
            "after_priority": round(float(after_priority), 6) if after_priority is not None else None,
            "priority_delta": priority_delta,
            "entered_ranking": entered_ranking,
            "left_ranking": left_ranking,
            "moved_up": entered_ranking or (rank_delta is not None and rank_delta < 0),
            "moved_down": left_ranking or (rank_delta is not None and rank_delta > 0),
        }
    return transitions


def _priority_by_goal(result: AgentCycleResult) -> dict[str, float]:
    return {intention.goal: intention.priority for intention in result.generated_intentions}


def _rank_by_goal(result: AgentCycleResult) -> dict[str, int]:
    ranked = sorted(result.generated_intentions, key=lambda item: (-item.priority, item.id))
    return {intention.goal: index for index, intention in enumerate(ranked, start=1)}


def _memory_for_intention(
    strategy_memory_bank: StrategyMemoryBank | None,
    intention: Intention,
) -> StrategyMemory | None:
    if strategy_memory_bank is None:
        return None
    return strategy_memory_bank.get(strategy_id_for_goal(intention.goal))


def _strategy_confidence_for_intention(
    strategy_memory_bank: StrategyMemoryBank | None,
    intention: Intention,
    experience_bias: ExperienceBias | None,
) -> float:
    strategy_memory = _memory_for_intention(strategy_memory_bank, intention)
    base_confidence = strategy_memory.confidence if strategy_memory else 0.50
    return round(
        max(
            0.0,
            min(1.0, base_confidence + _experience_confidence_delta_for_intention(intention, experience_bias)),
        ),
        6,
    )


def _experience_confidence_delta_for_intention(
    intention: Intention,
    experience_bias: ExperienceBias | None,
) -> float:
    if experience_bias is None:
        return 0.0
    strategy_id = strategy_id_for_goal(intention.goal)
    return round(
        float(experience_bias.strategy_confidence_delta_by_strategy.get(strategy_id, 0.0)),
        6,
    )


def _intention_to_dict(intention: Intention | None) -> dict[str, object] | None:
    if intention is None:
        return None
    return {
        "id": intention.id,
        "goal": intention.goal,
        "reason": intention.reason,
        "priority": intention.priority,
        "risk": intention.risk,
        "cost": intention.cost,
        "proposed_action": intention.proposed_action,
        "affordance": intention.affordance,
        "goal_id": intention.goal_id,
        "goal_description": intention.goal_description,
    }


def _gate_to_dict(gate: GateDecision) -> dict[str, object]:
    return {
        "status": gate.status,
        "reason": gate.reason,
        "allowed_as": gate.allowed_as,
    }


def _learning_update_to_dict(update: LearningUpdate) -> dict[str, object]:
    return {
        "belief_confidence_delta": update.belief_confidence_delta,
        "uncertainty_delta": update.uncertainty_delta,
        "prediction_error_delta": update.prediction_error_delta,
        "strategy_success_delta": update.strategy_success_delta,
        "pressure_bias_delta": dict(update.pressure_bias_delta),
        "reason": update.reason,
        "evidence_refs": list(update.evidence_refs),
        "learning_rate": update.learning_rate,
        "feedback_conflict": update.feedback_conflict,
        "effective_learning_rate": update.effective_learning_rate,
    }


def _dataclass_float_dict(value: object) -> dict[str, float]:
    data = asdict(value)
    return {str(key): round(float(item), 6) for key, item in data.items()}


def _delta(before: Mapping[str, float], after: Mapping[str, float]) -> dict[str, float]:
    return {
        key: round(float(after.get(key, 0.0)) - float(before.get(key, 0.0)), 6)
        for key in sorted(set(before).union(after))
    }
