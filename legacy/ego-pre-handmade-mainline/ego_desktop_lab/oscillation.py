from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.event_log import EvidenceRecord, append_evidence_record
from ego_desktop_lab.gate import GateDecision, evaluate_gate
from ego_desktop_lab.goal_progress import (
    FailureType,
    GoalProgressState,
    normalize_failure_type,
    update_goal_progress,
)
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.policy import INTENTION_SPECS
from ego_desktop_lab.reducer import AgentCycleResult, build_suggestion, run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState


@dataclass(frozen=True)
class OscillationConfig:
    hysteresis_margin: float = 0.05
    repair_cooldown_steps: int = 1
    high_risk_threshold: float = 0.85
    progress_epsilon: float = 0.03

    def __post_init__(self) -> None:
        object.__setattr__(self, "hysteresis_margin", max(0.0, float(self.hysteresis_margin)))
        object.__setattr__(self, "repair_cooldown_steps", max(0, int(self.repair_cooldown_steps)))
        object.__setattr__(self, "high_risk_threshold", clamp01(self.high_risk_threshold))
        object.__setattr__(self, "progress_epsilon", clamp01(self.progress_epsilon))


DEFAULT_OSCILLATION_CONFIG = OscillationConfig()


@dataclass(frozen=True)
class HysteresisDecision:
    blocked_by_hysteresis: bool
    reason: str
    current_goal: str | None
    candidate_goal: str | None
    priority_delta: float
    margin: float


@dataclass(frozen=True)
class CooldownDecision:
    blocked_by_cooldown: bool
    reason: str
    suppressed_goal: str | None
    replacement_goal: str | None
    risk: float
    high_risk_threshold: float


@dataclass(frozen=True)
class OscillationSelectionResult:
    selected_intention: Intention | None
    ranked_intentions: tuple[Intention, ...]
    oscillation_detected: bool
    routed_goal: str | None
    hysteresis_decision: HysteresisDecision
    cooldown_decision: CooldownDecision
    reason: str


@dataclass(frozen=True)
class OscillationControlCycleResult:
    raw_result: AgentCycleResult
    goal_progress_before: GoalProgressState
    goal_progress_after: GoalProgressState
    selection_result: OscillationSelectionResult
    gate_decision: GateDecision
    suggestion: str
    evidence_record: EvidenceRecord
    evidence_log_path: Path


def route_failure_type(failure_type: FailureType | str) -> str:
    normalized = normalize_failure_type(failure_type)
    if normalized == FailureType.evidence_failure:
        return "verify_before_claim"
    if normalized == FailureType.plan_failure:
        return "repair_or_replan_goal"
    if normalized == FailureType.goal_definition_failure:
        return "reframe_or_split_goal"
    if normalized == FailureType.permission_failure:
        return "ask_permission_or_defer"
    if normalized in {FailureType.execution_failure, FailureType.environment_failure}:
        return "retry_or_change_tool"
    raise ValueError(f"unsupported failure type: {failure_type}")


def apply_hysteresis(
    current: Intention | None,
    candidate: Intention | None,
    config: OscillationConfig = DEFAULT_OSCILLATION_CONFIG,
) -> HysteresisDecision:
    if current is None or candidate is None:
        return HysteresisDecision(False, "hysteresis not applicable", None, None, 0.0, config.hysteresis_margin)
    if current.goal == candidate.goal and current.goal_id == candidate.goal_id:
        return HysteresisDecision(
            False,
            "candidate matches current intention",
            current.goal,
            candidate.goal,
            0.0,
            config.hysteresis_margin,
        )
    priority_delta = round(candidate.priority - current.priority, 6)
    blocked = 0.0 < priority_delta < config.hysteresis_margin
    reason = (
        "candidate priority advantage is below hysteresis margin"
        if blocked
        else "candidate priority advantage clears hysteresis margin"
    )
    return HysteresisDecision(
        blocked_by_hysteresis=blocked,
        reason=reason,
        current_goal=current.goal,
        candidate_goal=candidate.goal,
        priority_delta=priority_delta,
        margin=config.hysteresis_margin,
    )


def apply_repair_cooldown(
    progress_state: GoalProgressState,
    ranked_intentions: tuple[Intention, ...],
    risk: float,
    config: OscillationConfig = DEFAULT_OSCILLATION_CONFIG,
) -> CooldownDecision:
    candidate = ranked_intentions[0] if ranked_intentions else None
    if candidate is None or candidate.goal != "repair_or_replan_goal":
        return CooldownDecision(False, "cooldown not applicable", None, None, risk, config.high_risk_threshold)
    recently_repaired = (
        progress_state.last_selected_intention == "repair_or_replan_goal"
        or progress_state.consecutive_repairs >= config.repair_cooldown_steps
    )
    if not recently_repaired or risk >= config.high_risk_threshold:
        return CooldownDecision(
            False,
            "repair allowed because cooldown is clear or risk is high",
            None,
            candidate.goal,
            risk,
            config.high_risk_threshold,
        )
    replacement = _first_non_repair(ranked_intentions)
    return CooldownDecision(
        True,
        "repair suppressed by cooldown",
        candidate.goal,
        replacement.goal if replacement else None,
        risk,
        config.high_risk_threshold,
    )


def select_with_oscillation_control(
    raw_intentions: tuple[Intention, ...],
    goal_progress: GoalProgressState,
    *,
    failure_type: FailureType | str | None = None,
    current_intention: Intention | None = None,
    risk: float | None = None,
    config: OscillationConfig = DEFAULT_OSCILLATION_CONFIG,
) -> OscillationSelectionResult:
    ranked = _rank_intentions(raw_intentions)
    base_candidate = ranked[0] if ranked else None
    candidate = base_candidate
    routed_goal: str | None = None
    hard_override = False
    reason_parts: list[str] = []

    if goal_progress.should_reframe:
        routed_goal = "reframe_or_split_goal"
        hard_override = True
        reason_parts.append("continue/repair oscillation triggered goal reframe")
    elif goal_progress.should_split:
        routed_goal = "split_goal_or_redefine_success_criteria"
        hard_override = True
        reason_parts.append("repeated repair without progress triggered goal split")
    elif failure_type is not None:
        routed_goal = route_failure_type(failure_type)
        hard_override = True
        reason_parts.append(f"{normalize_failure_type(failure_type).value} routed to {routed_goal}")

    if routed_goal and base_candidate is not None:
        candidate = _select_or_build_goal_intention(ranked, routed_goal, base_candidate)

    candidate_risk = risk if risk is not None else (candidate.risk if candidate is not None else 0.0)
    cooldown_ranked = _rank_intentions((candidate, *ranked)) if candidate is not None else ranked
    cooldown_decision = apply_repair_cooldown(goal_progress, cooldown_ranked, candidate_risk, config)
    if cooldown_decision.blocked_by_cooldown:
        replacement = _first_non_repair(ranked)
        if replacement is None and base_candidate is not None:
            replacement = _select_or_build_goal_intention(ranked, "verify_before_claim", base_candidate)
        candidate = replacement
        reason_parts.append(cooldown_decision.reason)

    hysteresis_decision = HysteresisDecision(
        False,
        "hysteresis skipped for hard oscillation/failure routing",
        current_intention.goal if current_intention else None,
        candidate.goal if candidate else None,
        0.0,
        config.hysteresis_margin,
    )
    if not hard_override and not cooldown_decision.blocked_by_cooldown:
        hysteresis_decision = apply_hysteresis(current_intention, candidate, config)
        if hysteresis_decision.blocked_by_hysteresis:
            candidate = current_intention
            reason_parts.append(hysteresis_decision.reason)

    oscillation_detected = bool(goal_progress.should_reframe or goal_progress.should_split)
    if not reason_parts:
        reason_parts.append("raw priority selection retained")

    selected_ranked = _rank_intentions((candidate, *ranked)) if candidate is not None else ranked
    return OscillationSelectionResult(
        selected_intention=candidate,
        ranked_intentions=selected_ranked,
        oscillation_detected=oscillation_detected,
        routed_goal=routed_goal,
        hysteresis_decision=hysteresis_decision,
        cooldown_decision=cooldown_decision,
        reason="; ".join(reason_parts),
    )


def run_oscillation_control_cycle(
    state: SubjectState,
    belief_state: BeliefState,
    goal_progress: GoalProgressState,
    *,
    outcome: OutcomeRecord | None,
    failure_type: FailureType | str | None,
    evidence_log_path: Path,
    timestamp: str,
    current_intention: Intention | None = None,
    append_evidence: bool = True,
    config: OscillationConfig = DEFAULT_OSCILLATION_CONFIG,
) -> OscillationControlCycleResult:
    raw_result = run_agent_cycle(
        state,
        evidence_log_path=evidence_log_path,
        timestamp=timestamp,
        belief_state=belief_state,
        append_evidence=False,
    )
    if raw_result.selected_intention is None:
        raise ValueError("oscillation control requires a raw selected intention")

    progress_after = update_goal_progress(
        goal_progress,
        raw_result.selected_intention,
        outcome,
        failure_type,
    )
    selection = select_with_oscillation_control(
        raw_result.generated_intentions,
        progress_after,
        failure_type=failure_type,
        current_intention=current_intention,
        risk=raw_result.selected_intention.risk,
        config=config,
    )
    if selection.selected_intention is None:
        gate_decision = raw_result.gate_decision
        suggestion = raw_result.suggestion
    else:
        gate_decision = evaluate_gate(selection.selected_intention.proposed_action)
        suggestion = build_suggestion(selection.selected_intention, gate_decision, state)

    normalized_failure = normalize_failure_type(failure_type)
    evidence_record = EvidenceRecord(
        event_id=f"event:oscillation:{goal_progress.goal_id}:{timestamp}",
        old_state_summary=raw_result.old_state_summary,
        belief_state=raw_result.belief_state,
        tensions=raw_result.tensions,
        appraisal=raw_result.appraisal,
        motivation_before=raw_result.motivation_before,
        motivation_after=raw_result.motivation_after,
        motivation_diff=raw_result.motivation_diff,
        motivation_pressure=raw_result.motivation_pressure,
        affordance_pressure=raw_result.affordance_pressure,
        generated_intentions=raw_result.generated_intentions,
        selected_intention=selection.selected_intention,
        gate_decision=gate_decision,
        suggestion=suggestion,
        timestamp=timestamp,
        previous_selected_intention=raw_result.selected_intention,
        outcome=outcome,
        goal_id=goal_progress.goal_id,
        goal_progress_before=goal_progress,
        goal_progress_after=progress_after,
        failure_type=normalized_failure.value if normalized_failure else None,
        oscillation_detected=selection.oscillation_detected,
        hysteresis_decision=selection.hysteresis_decision,
        cooldown_decision=selection.cooldown_decision,
        oscillation_selected_intention=selection.selected_intention,
        oscillation_reason=selection.reason,
        reason=selection.reason,
    )
    if append_evidence:
        append_evidence_record(evidence_log_path, evidence_record)

    return OscillationControlCycleResult(
        raw_result=raw_result,
        goal_progress_before=goal_progress,
        goal_progress_after=progress_after,
        selection_result=selection,
        gate_decision=gate_decision,
        suggestion=suggestion,
        evidence_record=evidence_record,
        evidence_log_path=evidence_log_path,
    )


def build_oscillation_control_report(output_path: Path) -> Path:
    from ego_desktop_lab.verification_pack import build_priority_table, load_scenario

    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    repair_scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_prediction_error_same_goal.json"))
    low_evidence_scenario = load_scenario(Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"))
    goal_id = scenario.state.unfinished_goals[0].goal_id
    report_log = Path("temp/ego_desktop_lab/oscillation_v3_5/report.jsonl")

    loop_progress = GoalProgressState(
        goal_id=goal_id,
        selection_history=(
            "continue_or_verify_unfinished_goal",
            "repair_or_replan_goal",
            "continue_or_verify_unfinished_goal",
        ),
        last_selected_intention="continue_or_verify_unfinished_goal",
        stagnation_count=3,
        consecutive_failures=3,
        repair_count=1,
    )
    loop_raw = run_agent_cycle(
        repair_scenario.state,
        evidence_log_path=report_log,
        timestamp=repair_scenario.timestamp,
        belief_state=repair_scenario.belief_state,
        append_evidence=False,
    )
    loop_outcome = OutcomeRecord(
        "oscillation_loop",
        loop_raw.selected_intention.id,
        loop_raw.selected_intention.goal,
        "repair should break oscillation",
        "repair_failure",
        0.10,
        "repair failed and no progress was made",
        0.80,
        ("report:loop",),
    )
    loop_case = run_oscillation_control_cycle(
        repair_scenario.state,
        repair_scenario.belief_state,
        loop_progress,
        outcome=loop_outcome,
        failure_type=FailureType.plan_failure,
        evidence_log_path=report_log,
        timestamp=repair_scenario.timestamp,
    )

    repeated_repair_case = select_with_oscillation_control(
        loop_raw.generated_intentions,
        GoalProgressState(
            goal_id=goal_id,
            progress_score=0.20,
            repair_count=2,
            consecutive_repairs=2,
            last_selected_intention="repair_or_replan_goal",
            should_split=True,
        ),
    )

    raw_ranked = _rank_intentions(loop_raw.generated_intentions)
    low_raw = run_agent_cycle(
        low_evidence_scenario.state,
        evidence_log_path=report_log,
        timestamp=low_evidence_scenario.timestamp,
        belief_state=low_evidence_scenario.belief_state,
        append_evidence=False,
    )
    low_ranked = _rank_intentions(low_raw.generated_intentions)
    candidate = low_ranked[0]
    current = _with_priority(low_ranked[1], candidate.priority - 0.03)
    hysteresis_case = select_with_oscillation_control(
        (candidate, current),
        GoalProgressState(goal_id=goal_id),
        current_intention=current,
    )

    cooldown_case = select_with_oscillation_control(
        raw_ranked,
        GoalProgressState(
            goal_id=goal_id,
            last_selected_intention="repair_or_replan_goal",
            consecutive_repairs=1,
        ),
        risk=0.10,
    )

    routing_case = {
        failure.value: route_failure_type(failure)
        for failure in (
            FailureType.evidence_failure,
            FailureType.plan_failure,
            FailureType.goal_definition_failure,
            FailureType.permission_failure,
            FailureType.execution_failure,
        )
    }

    lines = [
        "# Oscillation Control & Goal Progress Stability v3.5 Report",
        "",
        "Claim ceiling: lab-only deterministic oscillation-control proof.",
        "This report does not prove consciousness, life, live autonomy, runtime efficacy, or user benefit.",
        "",
        "## Continue/Repair Loop Case",
        "",
        f"- Final selected intention: `{loop_case.selection_result.selected_intention.goal}`",
        f"- Oscillation detected: `{loop_case.selection_result.oscillation_detected}`",
        f"- Reason: `{loop_case.selection_result.reason}`",
        "",
        "```json",
        json.dumps(
            {
                "goal_progress_before": asdict(loop_case.goal_progress_before),
                "goal_progress_after": asdict(loop_case.goal_progress_after),
                "raw_priority_ranking": build_priority_table(loop_case.raw_result),
                "evidence_log_path": str(loop_case.evidence_log_path),
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "## Repeated Repair Case",
        "",
        "```json",
        json.dumps(asdict(repeated_repair_case), indent=2, sort_keys=True),
        "```",
        "",
        "## Hysteresis Case",
        "",
        "```json",
        json.dumps(asdict(hysteresis_case.hysteresis_decision), indent=2, sort_keys=True),
        "```",
        "",
        "## Cooldown Case",
        "",
        "```json",
        json.dumps(asdict(cooldown_case.cooldown_decision), indent=2, sort_keys=True),
        "```",
        "",
        "## Failure Type Routing Case",
        "",
        "```json",
        json.dumps(routing_case, indent=2, sort_keys=True),
        "```",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _rank_intentions(intentions: tuple[Intention | None, ...]) -> tuple[Intention, ...]:
    concrete = tuple(intention for intention in intentions if intention is not None)
    return tuple(sorted(concrete, key=lambda item: (-item.priority, item.id)))


def _first_non_repair(intentions: tuple[Intention, ...]) -> Intention | None:
    for intention in intentions:
        if intention.goal != "repair_or_replan_goal":
            return intention
    return None


def _select_or_build_goal_intention(
    ranked_intentions: tuple[Intention, ...],
    goal: str,
    base_intention: Intention,
) -> Intention:
    for intention in ranked_intentions:
        if intention.goal == goal:
            return intention
    return _build_control_intention(goal, base_intention)


def _build_control_intention(goal: str, base_intention: Intention) -> Intention:
    spec = INTENTION_SPECS[goal]
    return Intention(
        id=f"intention:oscillation:{goal}:{base_intention.goal_id or 'goal:none'}",
        goal=goal,
        reason=str(spec["reason"]),
        source_tension=base_intention.source_tension,
        priority=round(base_intention.priority + 0.2, 6),
        risk=float(spec["risk"]),
        cost=float(spec["cost"]),
        proposed_action=str(spec["proposed_action"]),
        affordance=str(spec["affordance"]),
        goal_id=base_intention.goal_id,
        goal_description=base_intention.goal_description,
    )


def _with_priority(intention: Intention, priority: float) -> Intention:
    return Intention(
        id=intention.id,
        goal=intention.goal,
        reason=intention.reason,
        source_tension=intention.source_tension,
        priority=round(priority, 6),
        risk=intention.risk,
        cost=intention.cost,
        proposed_action=intention.proposed_action,
        affordance=intention.affordance,
        goal_id=intention.goal_id,
        goal_description=intention.goal_description,
    )
