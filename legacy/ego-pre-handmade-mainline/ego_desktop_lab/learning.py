from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.event_log import EvidenceRecord, append_evidence_record
from ego_desktop_lab.outcome import OutcomeRecord, strategy_id_for_goal
from ego_desktop_lab.pressure import MotivationPressure
from ego_desktop_lab.stability import (
    DEFAULT_LEARNING_CONFIG,
    LearningConfig,
    detect_feedback_conflict,
    effective_learning_rate,
)
from ego_desktop_lab.strategy_memory import (
    StrategyMemory,
    StrategyMemoryBank,
    default_strategy_memory,
    update_strategy_memory,
)
from ego_desktop_lab.subject_state import SubjectState


PRESSURE_KEYS = (
    "viability_error",
    "prediction_error",
    "commitment_error",
    "boundary_error",
    "uncertainty_precision",
)


@dataclass(frozen=True)
class LearningUpdate:
    belief_confidence_delta: float
    uncertainty_delta: float
    prediction_error_delta: float
    strategy_success_delta: float
    pressure_bias_delta: dict[str, float]
    reason: str
    evidence_refs: tuple[str, ...]
    learning_rate: float = 0.35
    feedback_conflict: bool = False
    effective_learning_rate: float = 0.35

    def __post_init__(self) -> None:
        object.__setattr__(self, "pressure_bias_delta", _normalize_pressure_bias(self.pressure_bias_delta))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True)
class LearningCycleResult:
    before_result: Any
    outcome: OutcomeRecord
    learning_update: LearningUpdate
    strategy_memory_before: StrategyMemoryBank
    strategy_memory_after: StrategyMemoryBank
    updated_state: SubjectState
    updated_belief_state: BeliefState
    next_result: Any
    evidence_record: EvidenceRecord
    evidence_log_path: Path


def derive_learning_update(
    outcome: OutcomeRecord,
    config: LearningConfig = DEFAULT_LEARNING_CONFIG,
) -> LearningUpdate:
    strategy_id = strategy_id_for_goal(outcome.selected_plan_id)
    success = outcome.success_score
    failure = 1.0 - success
    feedback_conflict = detect_feedback_conflict(outcome)
    rate = effective_learning_rate(config, outcome)

    if strategy_id == "verify" and success >= 0.65:
        return LearningUpdate(
            belief_confidence_delta=_scale(0.50 * success, rate),
            uncertainty_delta=_scale(-0.55 * success, rate),
            prediction_error_delta=_scale(-0.30 * success, rate),
            strategy_success_delta=success,
            pressure_bias_delta={
                "uncertainty_precision": _scale(-0.55 * success, rate),
                "prediction_error": _scale(-0.30 * success, rate),
            },
            reason="verify_before_claim succeeded, so uncertainty and verify pressure are reduced.",
            evidence_refs=outcome.evidence_refs,
            learning_rate=config.learning_rate,
            feedback_conflict=feedback_conflict,
            effective_learning_rate=rate,
        )

    if strategy_id == "continue_goal" and success < 0.65:
        return LearningUpdate(
            belief_confidence_delta=_scale(-0.23 * failure, rate),
            uncertainty_delta=_scale(0.23 * failure, rate),
            prediction_error_delta=_scale(2.29 * max(failure, outcome.prediction_error), rate),
            strategy_success_delta=round(-failure, 6),
            pressure_bias_delta={
                "viability_error": _scale(2.00 * failure, rate),
                "prediction_error": _scale(2.29 * max(failure, outcome.prediction_error), rate),
            },
            reason="continuing failed, so prediction and viability error shift pressure toward repair.",
            evidence_refs=outcome.evidence_refs,
            learning_rate=config.learning_rate,
            feedback_conflict=feedback_conflict,
            effective_learning_rate=rate,
        )

    if strategy_id == "repair" and success >= 0.65:
        return LearningUpdate(
            belief_confidence_delta=_scale(0.514 * success, rate),
            uncertainty_delta=_scale(-0.343 * success, rate),
            prediction_error_delta=_scale(-0.714 * success, rate),
            strategy_success_delta=success,
            pressure_bias_delta={
                "viability_error": _scale(-0.571 * success, rate),
                "prediction_error": _scale(-0.714 * success, rate),
            },
            reason="repair succeeded, so prediction error drops and repair strategy confidence rises.",
            evidence_refs=outcome.evidence_refs,
            learning_rate=config.learning_rate,
            feedback_conflict=feedback_conflict,
            effective_learning_rate=rate,
        )

    if strategy_id == "preserve_identity" and success >= 0.65:
        return LearningUpdate(
            belief_confidence_delta=_scale(0.429 * success, rate),
            uncertainty_delta=_scale(-0.286 * success, rate),
            prediction_error_delta=_scale(-0.229 * success, rate),
            strategy_success_delta=success,
            pressure_bias_delta={
                "boundary_error": _scale(-0.714 * success, rate),
                "uncertainty_precision": _scale(-0.229 * success, rate),
            },
            reason="identity boundary protection succeeded, so boundary pressure stabilizes.",
            evidence_refs=outcome.evidence_refs,
            learning_rate=config.learning_rate,
            feedback_conflict=feedback_conflict,
            effective_learning_rate=rate,
        )

    return LearningUpdate(
        belief_confidence_delta=_scale((success - 0.50) * 0.30, rate),
        uncertainty_delta=_scale((0.50 - success) * 0.30, rate),
        prediction_error_delta=_scale((outcome.prediction_error - success) * 0.30, rate),
        strategy_success_delta=round(success - 0.50, 6),
        pressure_bias_delta={},
        reason="generic bounded learning update from outcome score.",
        evidence_refs=outcome.evidence_refs,
        learning_rate=config.learning_rate,
        feedback_conflict=feedback_conflict,
        effective_learning_rate=rate,
    )


def apply_learning_to_state(
    state: SubjectState,
    outcome: OutcomeRecord,
    update: LearningUpdate,
) -> SubjectState:
    strategy_id = strategy_id_for_goal(outcome.selected_plan_id)
    recent_failures = tuple(state.recent_failures)
    identity_conflict = state.identity_conflict
    integrity = state.integrity

    if update.strategy_success_delta < 0:
        failure_marker = f"outcome_failure:{outcome.scenario_id}:{strategy_id}"
        if failure_marker not in recent_failures:
            recent_failures = (failure_marker, *recent_failures)[:3]
    elif strategy_id == "repair":
        recent_failures = ()

    if strategy_id == "preserve_identity" and update.strategy_success_delta > 0:
        identity_conflict = False
        integrity = clamp01(integrity + 0.12)

    return replace(
        state,
        uncertainty=clamp01(state.uncertainty + update.uncertainty_delta),
        integrity=integrity,
        recent_failures=recent_failures,
        identity_conflict=identity_conflict,
    )


def apply_learning_to_belief(
    belief: BeliefState,
    outcome: OutcomeRecord,
    update: LearningUpdate,
) -> BeliefState:
    known_facts = tuple(belief.known_facts)
    unknowns = tuple(belief.unknowns)
    assumptions = tuple(belief.assumptions)
    evidence_strength = belief.evidence_strength

    if update.strategy_success_delta > 0:
        fact = f"outcome_success:{outcome.scenario_id}:{strategy_id_for_goal(outcome.selected_plan_id)}"
        if fact not in known_facts:
            known_facts = (*known_facts, fact)
        if unknowns:
            unknowns = unknowns[1:]
        if update.prediction_error_delta < 0 and assumptions:
            assumptions = assumptions[1:]
        evidence_strength = clamp01(evidence_strength + max(0.0, update.belief_confidence_delta * 0.50))
    elif update.strategy_success_delta < 0:
        unknown = f"outcome_failure_unknown:{outcome.scenario_id}:{strategy_id_for_goal(outcome.selected_plan_id)}"
        assumption = f"outcome_failure_assumption:{outcome.scenario_id}:{strategy_id_for_goal(outcome.selected_plan_id)}"
        if unknown not in unknowns:
            unknowns = (*unknowns, unknown)
        if assumption not in assumptions:
            assumptions = (*assumptions, assumption)
        evidence_strength = clamp01(evidence_strength + min(0.0, update.belief_confidence_delta * 0.50))

    return BeliefState(
        known_facts=known_facts,
        unknowns=unknowns,
        assumptions=assumptions,
        evidence_strength=evidence_strength,
        confidence=clamp01(belief.confidence + update.belief_confidence_delta),
    )


def apply_pressure_bias(
    pressure: MotivationPressure,
    pressure_bias_delta: dict[str, float] | None,
) -> MotivationPressure:
    bias = pressure_bias_delta or {}
    return MotivationPressure(
        viability_error=pressure.viability_error + bias.get("viability_error", 0.0),
        prediction_error=pressure.prediction_error + bias.get("prediction_error", 0.0),
        commitment_error=pressure.commitment_error + bias.get("commitment_error", 0.0),
        boundary_error=pressure.boundary_error + bias.get("boundary_error", 0.0),
        uncertainty_precision=pressure.uncertainty_precision + bias.get("uncertainty_precision", 0.0),
    )


def run_learning_cycle(
    state: SubjectState,
    belief_state: BeliefState,
    outcome: OutcomeRecord,
    *,
    evidence_log_path: Path,
    timestamp: str,
    strategy_memory_bank: StrategyMemoryBank | None = None,
    config: LearningConfig = DEFAULT_LEARNING_CONFIG,
    initial_pressure_bias: dict[str, float] | None = None,
) -> LearningCycleResult:
    from ego_desktop_lab.reducer import run_agent_cycle

    bank = dict(strategy_memory_bank or {})
    before_result = run_agent_cycle(
        state,
        evidence_log_path=evidence_log_path,
        timestamp=timestamp,
        belief_state=belief_state,
        pressure_bias=initial_pressure_bias,
        append_evidence=False,
    )
    if before_result.selected_intention is None:
        raise ValueError("learning cycle requires a previous selected intention")
    if outcome.selected_intention_id != before_result.selected_intention.id:
        raise ValueError("outcome selected_intention_id does not match the previous selected intention")
    if outcome.selected_plan_id != before_result.selected_intention.goal:
        raise ValueError("outcome selected_plan_id does not match the previous selected intention goal")

    learning_update = derive_learning_update(outcome, config)
    strategy_id = strategy_id_for_goal(outcome.selected_plan_id)
    memory_before = {**bank, strategy_id: bank.get(strategy_id, default_strategy_memory(strategy_id))}
    memory_after = update_strategy_memory(
        memory_before,
        outcome,
        timestamp,
        config=config,
        feedback_conflict=learning_update.feedback_conflict,
    )
    updated_state = apply_learning_to_state(state, outcome, learning_update)
    updated_belief = apply_learning_to_belief(belief_state, outcome, learning_update)
    next_result = run_agent_cycle(
        updated_state,
        evidence_log_path=evidence_log_path,
        timestamp=timestamp,
        belief_state=updated_belief,
        pressure_bias=merge_pressure_bias(initial_pressure_bias, learning_update.pressure_bias_delta),
        append_evidence=False,
    )
    evidence_record = EvidenceRecord(
        event_id=f"event:learning:{outcome.scenario_id}:{timestamp}",
        old_state_summary=next_result.old_state_summary,
        belief_state=next_result.belief_state,
        tensions=next_result.tensions,
        appraisal=next_result.appraisal,
        motivation_before=next_result.motivation_before,
        motivation_after=next_result.motivation_after,
        motivation_diff=next_result.motivation_diff,
        motivation_pressure=next_result.motivation_pressure,
        affordance_pressure=next_result.affordance_pressure,
        generated_intentions=next_result.generated_intentions,
        selected_intention=next_result.selected_intention,
        gate_decision=next_result.gate_decision,
        suggestion=next_result.suggestion,
        timestamp=timestamp,
        previous_selected_intention=before_result.selected_intention,
        outcome=outcome,
        learning_update=learning_update,
        strategy_memory_before=memory_before,
        strategy_memory_after=memory_after,
        next_appraisal=next_result.appraisal,
        next_motivation_pressure=next_result.motivation_pressure,
        next_affordance_pressure=next_result.affordance_pressure,
        next_generated_intentions=next_result.generated_intentions,
        next_selected_intention=next_result.selected_intention,
        feedback_conflict=learning_update.feedback_conflict,
    )
    append_evidence_record(evidence_log_path, evidence_record)
    return LearningCycleResult(
        before_result=before_result,
        outcome=outcome,
        learning_update=learning_update,
        strategy_memory_before=memory_before,
        strategy_memory_after=memory_after,
        updated_state=updated_state,
        updated_belief_state=updated_belief,
        next_result=next_result,
        evidence_record=evidence_record,
        evidence_log_path=evidence_log_path,
    )


def build_outcome_learning_report(output_path: Path) -> Path:
    from ego_desktop_lab.reducer import run_agent_cycle
    from ego_desktop_lab.verification_pack import DEFAULT_REPORT_SCENARIOS, build_priority_table, load_scenario

    lines = [
        "# Outcome Learning v2 Report",
        "",
        "Claim ceiling: lab-only deterministic outcome-learning proof.",
        "This report does not prove consciousness, life, live autonomy, runtime efficacy, or user benefit.",
        "",
        "## Summary",
        "",
        "| Scenario | Outcome | Before selected | After selected | Expected change observed |",
        "|---|---|---|---|---|",
    ]
    details: list[str] = []

    for scenario_path in DEFAULT_REPORT_SCENARIOS:
        scenario = load_scenario(scenario_path)
        before_probe = run_agent_cycle(
            scenario.state,
            evidence_log_path=scenario.evidence_log_path,
            timestamp=scenario.timestamp,
            belief_state=scenario.belief_state,
            append_evidence=False,
        )
        if before_probe.selected_intention is None:
            raise ValueError(f"scenario {scenario.name} produced no selected intention")

        outcome = _default_outcome_for_selected(
            scenario.name,
            before_probe.selected_intention.id,
            before_probe.selected_intention.goal,
        )
        result = run_learning_cycle(
            scenario.state,
            scenario.belief_state,
            outcome,
            evidence_log_path=Path(f"temp/ego_desktop_lab/outcome_learning_v2/{scenario.name}.jsonl"),
            timestamp=scenario.timestamp,
        )
        before_selected = result.before_result.selected_intention.goal if result.before_result.selected_intention else "none"
        after_selected = result.next_result.selected_intention.goal if result.next_result.selected_intention else "none"
        observed = _expected_learning_change_observed(result)
        lines.append(
            f"| {scenario.name} | {outcome.actual_effect} | `{before_selected}` | "
            f"`{after_selected}` | `{observed}` |"
        )
        details.extend(_learning_detail_lines(result, build_priority_table))

    lines.extend(["", "## Scenario Details", ""])
    lines.extend(details)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _normalize_pressure_bias(pressure_bias_delta: dict[str, float]) -> dict[str, float]:
    return {key: round(float(pressure_bias_delta.get(key, 0.0)), 6) for key in PRESSURE_KEYS}


def merge_pressure_bias(
    base: dict[str, float] | None,
    delta: dict[str, float] | None,
) -> dict[str, float]:
    base_bias = _normalize_pressure_bias(base or {})
    delta_bias = _normalize_pressure_bias(delta or {})
    return {
        key: round(max(-1.0, min(1.0, base_bias.get(key, 0.0) + delta_bias.get(key, 0.0))), 6)
        for key in PRESSURE_KEYS
    }


def _scale(value: float, rate: float) -> float:
    return round(value * rate, 6)


def _default_outcome_for_selected(
    scenario_id: str,
    selected_intention_id: str,
    selected_plan_id: str,
) -> OutcomeRecord:
    if selected_plan_id == "verify_before_claim":
        return OutcomeRecord(
            scenario_id=scenario_id,
            selected_intention_id=selected_intention_id,
            selected_plan_id=selected_plan_id,
            expected_effect="reduce uncertainty before claiming",
            actual_effect="verify_success",
            success_score=0.90,
            user_feedback="verification reduced uncertainty",
            prediction_error=0.05,
            evidence_refs=(f"scenario:{scenario_id}",),
        )
    if selected_plan_id == "continue_or_verify_unfinished_goal":
        return OutcomeRecord(
            scenario_id=scenario_id,
            selected_intention_id=selected_intention_id,
            selected_plan_id=selected_plan_id,
            expected_effect="continue goal without repair",
            actual_effect="continue_failure",
            success_score=0.10,
            user_feedback="continuation failed and needs repair",
            prediction_error=0.90,
            evidence_refs=(f"scenario:{scenario_id}",),
        )
    if selected_plan_id == "repair_or_replan_goal":
        return OutcomeRecord(
            scenario_id=scenario_id,
            selected_intention_id=selected_intention_id,
            selected_plan_id=selected_plan_id,
            expected_effect="repair failed goal path",
            actual_effect="repair_success",
            success_score=0.92,
            user_feedback="repair reduced prediction error",
            prediction_error=0.08,
            evidence_refs=(f"scenario:{scenario_id}",),
        )
    if selected_plan_id == "preserve_identity_boundary":
        return OutcomeRecord(
            scenario_id=scenario_id,
            selected_intention_id=selected_intention_id,
            selected_plan_id=selected_plan_id,
            expected_effect="protect identity boundary",
            actual_effect="identity_protection_success",
            success_score=0.90,
            user_feedback="identity boundary was protected",
            prediction_error=0.05,
            evidence_refs=(f"scenario:{scenario_id}",),
        )
    raise ValueError(f"unsupported selected plan: {selected_plan_id}")


def _expected_learning_change_observed(result: LearningCycleResult) -> bool:
    goal = result.outcome.selected_plan_id
    if goal == "verify_before_claim":
        return (
            result.next_result.appraisal.uncertainty_delta < result.before_result.appraisal.uncertainty_delta
            and result.next_result.affordance_pressure["verify"]
            <= result.before_result.affordance_pressure["verify"]
        )
    if goal == "continue_or_verify_unfinished_goal":
        before_repair = _priority_for_goal(result.before_result, "repair_or_replan_goal")
        after_repair = _priority_for_goal(result.next_result, "repair_or_replan_goal")
        return (
            result.next_result.appraisal.prediction_error > result.before_result.appraisal.prediction_error
            and result.next_result.affordance_pressure["repair"]
            > result.before_result.affordance_pressure["repair"]
            and after_repair > before_repair
        )
    if goal == "repair_or_replan_goal":
        return (
            result.next_result.appraisal.prediction_error < result.before_result.appraisal.prediction_error
            and result.updated_belief_state.confidence > result.before_result.belief_state.confidence
        )
    if goal == "preserve_identity_boundary":
        return (
            result.next_result.affordance_pressure["preserve_identity"]
            <= result.before_result.affordance_pressure["preserve_identity"]
        )
    return False


def _priority_for_goal(result: Any, goal: str) -> float:
    for intention in result.generated_intentions:
        if intention.goal == goal:
            return intention.priority
    return -999.0


def _learning_detail_lines(result: LearningCycleResult, priority_table_builder: Any) -> list[str]:
    before_selected = result.before_result.selected_intention.goal if result.before_result.selected_intention else "none"
    after_selected = result.next_result.selected_intention.goal if result.next_result.selected_intention else "none"
    lines = [
        f"### {result.outcome.scenario_id}",
        "",
        f"- Before selected intention: `{before_selected}`",
        f"- After selected intention: `{after_selected}`",
        f"- Expected change observed: `{_expected_learning_change_observed(result)}`",
        f"- Evidence log path: `{result.evidence_log_path}`",
        "",
        "Outcome record:",
        "",
        "```json",
        json.dumps(asdict(result.outcome), indent=2, sort_keys=True),
        "```",
        "",
        "Learning update:",
        "",
        "```json",
        json.dumps(asdict(result.learning_update), indent=2, sort_keys=True),
        "```",
        "",
        "Strategy memory before / after:",
        "",
        "```json",
        json.dumps(
            {
                "before": {key: asdict(value) for key, value in result.strategy_memory_before.items()},
                "after": {key: asdict(value) for key, value in result.strategy_memory_after.items()},
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "Before pressure map:",
        "",
        "| Affordance | Pressure |",
        "|---|---:|",
    ]
    for name, pressure in sorted(result.before_result.affordance_pressure.items()):
        lines.append(f"| `{name}` | {pressure} |")
    lines.extend(["", "After pressure map:", "", "| Affordance | Pressure |", "|---|---:|"])
    for name, pressure in sorted(result.next_result.affordance_pressure.items()):
        lines.append(f"| `{name}` | {pressure} |")

    lines.extend(["", "Before priority ranking:", "", "| Rank | Goal | Priority | Affordance | Source tension | Action |", "|---:|---|---:|---|---|---|"])
    for row in priority_table_builder(result.before_result):
        lines.append(
            f"| {row['rank']} | `{row['goal']}` | {row['priority']} | "
            f"`{row['affordance']}` | `{row['source_tension']}` | `{row['proposed_action']}` |"
        )
    lines.extend(["", "After priority ranking:", "", "| Rank | Goal | Priority | Affordance | Source tension | Action |", "|---:|---|---:|---|---|---|"])
    for row in priority_table_builder(result.next_result):
        lines.append(
            f"| {row['rank']} | `{row['goal']}` | {row['priority']} | "
            f"`{row['affordance']}` | `{row['source_tension']}` | `{row['proposed_action']}` |"
        )
    lines.append("")
    return lines
