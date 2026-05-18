from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.strategy_memory import StrategyMemory, StrategyMemoryBank
from ego_desktop_lab.subject_state import SubjectState


@dataclass(frozen=True)
class LearningConfig:
    learning_rate: float = 0.35
    conflict_learning_rate_multiplier: float = 0.35
    confidence_min: float = 0.15
    confidence_max: float = 0.85
    baseline_confidence: float = 0.50
    decay_rate: float = 0.10

    def __post_init__(self) -> None:
        object.__setattr__(self, "learning_rate", clamp01(self.learning_rate))
        object.__setattr__(
            self,
            "conflict_learning_rate_multiplier",
            clamp01(self.conflict_learning_rate_multiplier),
        )
        object.__setattr__(self, "confidence_min", clamp01(self.confidence_min))
        object.__setattr__(self, "confidence_max", clamp01(self.confidence_max))
        object.__setattr__(self, "baseline_confidence", clamp01(self.baseline_confidence))
        object.__setattr__(self, "decay_rate", clamp01(self.decay_rate))


DEFAULT_LEARNING_CONFIG = LearningConfig()


@dataclass(frozen=True)
class LearningSequenceResult:
    trace: tuple[Any, ...]
    final_state: SubjectState
    final_belief_state: BeliefState
    final_strategy_memory: StrategyMemoryBank
    final_result: Any
    pressure_stability_table: tuple[dict[str, object], ...]


def detect_feedback_conflict(outcome: OutcomeRecord) -> bool:
    actual = outcome.actual_effect.lower()
    feedback = outcome.user_feedback.lower()
    success_effect = any(token in actual for token in ("success", "succeeded", "resolved", "protected"))
    failure_effect = any(token in actual for token in ("failure", "failed", "blocked", "regressed"))
    positive_feedback = any(
        token in feedback for token in ("success", "worked", "good", "reduced", "resolved", "protected")
    )
    negative_feedback = any(
        token in feedback for token in ("fail", "failed", "not", "no ", "wrong", "bad", "regressed")
    )
    if success_effect and (negative_feedback or outcome.success_score < 0.40):
        return True
    if failure_effect and (positive_feedback or outcome.success_score > 0.60):
        return True
    return False


def effective_learning_rate(
    config: LearningConfig,
    outcome: OutcomeRecord,
) -> float:
    rate = config.learning_rate
    if detect_feedback_conflict(outcome):
        rate *= config.conflict_learning_rate_multiplier
    return round(rate, 6)


def clamp_confidence(value: float, config: LearningConfig = DEFAULT_LEARNING_CONFIG) -> float:
    return round(max(config.confidence_min, min(config.confidence_max, value)), 6)


def decay_strategy_memory(
    bank: StrategyMemoryBank,
    inactive_strategy_ids: tuple[str, ...],
    *,
    steps: int,
    config: LearningConfig = DEFAULT_LEARNING_CONFIG,
) -> StrategyMemoryBank:
    decay_factor = (1.0 - config.decay_rate) ** max(0, steps)
    updated = dict(bank)
    for strategy_id in inactive_strategy_ids:
        memory = updated.get(strategy_id)
        if memory is None:
            continue
        confidence = config.baseline_confidence + (
            (memory.confidence - config.baseline_confidence) * decay_factor
        )
        updated[strategy_id] = StrategyMemory(
            strategy_id=memory.strategy_id,
            success_count=memory.success_count,
            failure_count=memory.failure_count,
            average_success_score=memory.average_success_score,
            last_used_at=memory.last_used_at,
            confidence=clamp_confidence(confidence, config),
        )
    return updated


def run_learning_sequence(
    state: SubjectState,
    belief_state: BeliefState,
    outcome_specs: tuple[dict[str, object], ...],
    *,
    evidence_log_path: Path,
    timestamp: str,
    config: LearningConfig = DEFAULT_LEARNING_CONFIG,
) -> LearningSequenceResult:
    from ego_desktop_lab.learning import run_learning_cycle
    from ego_desktop_lab.reducer import run_agent_cycle

    current_state = state
    current_belief = belief_state
    strategy_memory: StrategyMemoryBank = {}
    trace: list[Any] = []
    pressure_rows: list[dict[str, object]] = []
    final_result: Any = None
    cumulative_pressure_bias: dict[str, float] | None = None

    for index, spec in enumerate(outcome_specs, start=1):
        step_timestamp = f"{timestamp}:step:{index:03d}"
        before = run_agent_cycle(
            current_state,
            evidence_log_path=evidence_log_path,
            timestamp=step_timestamp,
            belief_state=current_belief,
            pressure_bias=cumulative_pressure_bias,
            append_evidence=False,
        )
        if before.selected_intention is None:
            raise ValueError("learning sequence requires a selected intention at every step")
        outcome = OutcomeRecord(
            scenario_id=str(spec.get("scenario_id", f"sequence_step_{index:03d}")),
            selected_intention_id=before.selected_intention.id,
            selected_plan_id=before.selected_intention.goal,
            expected_effect=str(spec.get("expected_effect", "bounded learning sequence step")),
            actual_effect=str(spec["actual_effect"]),
            success_score=float(spec["success_score"]),
            user_feedback=str(spec["user_feedback"]),
            prediction_error=float(spec["prediction_error"]),
            evidence_refs=tuple(str(item) for item in spec.get("evidence_refs", (f"sequence:{index}",))),
        )
        result = run_learning_cycle(
            current_state,
            current_belief,
            outcome,
            evidence_log_path=evidence_log_path,
            timestamp=step_timestamp,
            strategy_memory_bank=strategy_memory,
            config=config,
            initial_pressure_bias=cumulative_pressure_bias,
        )
        trace.append(result)
        pressure_rows.append(
            {
                "step": index,
                "selected_before": before.selected_intention.goal,
                "selected_after": result.next_result.selected_intention.goal
                if result.next_result.selected_intention
                else "none",
                "pressure_before": before.affordance_pressure,
                "pressure_after": result.next_result.affordance_pressure,
            }
        )
        current_state = result.updated_state
        current_belief = result.updated_belief_state
        strategy_memory = result.strategy_memory_after
        final_result = result.next_result
        from ego_desktop_lab.learning import merge_pressure_bias

        cumulative_pressure_bias = merge_pressure_bias(
            cumulative_pressure_bias,
            result.learning_update.pressure_bias_delta,
        )

    if final_result is None:
        final_result = run_agent_cycle(
            current_state,
            evidence_log_path=evidence_log_path,
            timestamp=timestamp,
            belief_state=current_belief,
            pressure_bias=cumulative_pressure_bias,
            append_evidence=False,
        )

    return LearningSequenceResult(
        trace=tuple(trace),
        final_state=current_state,
        final_belief_state=current_belief,
        final_strategy_memory=strategy_memory,
        final_result=final_result,
        pressure_stability_table=tuple(pressure_rows),
    )


def build_stability_generalization_report(output_path: Path) -> Path:
    from ego_desktop_lab.learning import derive_learning_update
    from ego_desktop_lab.reducer import run_agent_cycle
    from ego_desktop_lab.strategy_memory import update_strategy_memory
    from ego_desktop_lab.subject_state import SubjectState
    from ego_desktop_lab.verification_pack import build_priority_table, load_scenario

    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    sequence = (
        {
            "scenario_id": "report_continue_failure",
            "actual_effect": "continue_failure",
            "success_score": 0.10,
            "user_feedback": "continuation failed and needs repair",
            "prediction_error": 0.90,
        },
        {
            "scenario_id": "report_repair_success",
            "actual_effect": "repair_success",
            "success_score": 0.90,
            "user_feedback": "repair worked and reduced prediction error",
            "prediction_error": 0.10,
        },
        {
            "scenario_id": "report_continue_failure_again",
            "actual_effect": "continue_failure",
            "success_score": 0.20,
            "user_feedback": "continuation regressed again",
            "prediction_error": 0.80,
        },
    )
    sequence_result = run_learning_sequence(
        scenario.state,
        scenario.belief_state,
        sequence,
        evidence_log_path=Path("temp/ego_desktop_lab/stability_v3/multistep.jsonl"),
        timestamp=scenario.timestamp,
    )

    normal = OutcomeRecord(
        scenario.name,
        "intention:002:verify_before_claim",
        "verify_before_claim",
        "reduce uncertainty",
        "verify_success",
        0.90,
        "verification worked and reduced uncertainty",
        0.05,
        ("report:normal_feedback",),
    )
    noisy = OutcomeRecord(
        scenario.name,
        "intention:002:verify_before_claim",
        "verify_before_claim",
        "reduce uncertainty",
        "verify_success",
        0.90,
        "not useful and failed",
        0.05,
        ("report:noisy_feedback",),
    )
    normal_update = derive_learning_update(normal)
    noisy_update = derive_learning_update(noisy)

    conflicting_bank: StrategyMemoryBank = {}
    for index, outcome in enumerate(
        (
            OutcomeRecord("conflicting", "intention:001:repair_or_replan_goal", "repair_or_replan_goal", "repair", "repair_success", 0.90, "repair worked", 0.10, ("report:success1",)),
            OutcomeRecord("conflicting", "intention:001:repair_or_replan_goal", "repair_or_replan_goal", "repair", "repair_failure", 0.20, "repair failed", 0.80, ("report:failure",)),
            OutcomeRecord("conflicting", "intention:001:repair_or_replan_goal", "repair_or_replan_goal", "repair", "repair_success", 0.80, "repair recovered", 0.20, ("report:success2",)),
        ),
        start=1,
    ):
        conflicting_bank = update_strategy_memory(
            conflicting_bank,
            outcome,
            f"2026-05-12T00:0{index}:00+00:00",
        )

    decayed_memory = decay_strategy_memory(conflicting_bank, ("repair",), steps=3)

    multi_goal_state = SubjectState(
        agent_id="report-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.72,
        risk_sensitivity=0.60,
        unfinished_goals=(
            {"goal_id": "goal:low", "description": "low salience documentation cleanup", "salience": 0.10},
            {"goal_id": "goal:high", "description": "high salience repair proof", "salience": 0.95},
        ),
        recent_failures=(),
        identity_conflict=False,
    )
    multi_goal_result = run_agent_cycle(
        multi_goal_state,
        evidence_log_path=Path("temp/ego_desktop_lab/stability_v3/multi_goal.jsonl"),
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=BeliefState(("evidence exists",), (), (), 0.95, 0.92),
        append_evidence=False,
    )

    lines = [
        "# Stability & Generalization Pack v3 Report",
        "",
        "Claim ceiling: lab-only deterministic stability/generalization proof.",
        "This report does not prove consciousness, life, live autonomy, runtime efficacy, or user benefit.",
        "",
        "## Multi-step Learning Trace",
        "",
        "| Step | Before selected | After selected |",
        "|---:|---|---|",
    ]
    for row in sequence_result.pressure_stability_table:
        lines.append(f"| {row['step']} | `{row['selected_before']}` | `{row['selected_after']}` |")

    lines.extend(["", "## Before / After Strategy Memory", "", "```json"])
    lines.append(
        json.dumps(
            {
                "final_strategy_memory": {
                    key: asdict(value) for key, value in sequence_result.final_strategy_memory.items()
                },
                "conflicting_outcomes_memory": {
                    key: asdict(value) for key, value in conflicting_bank.items()
                },
                "decayed_memory": {key: asdict(value) for key, value in decayed_memory.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )
    lines.extend(["```", "", "## Pressure Stability Table", "", "```json"])
    lines.append(json.dumps(sequence_result.pressure_stability_table, indent=2, sort_keys=True))
    lines.extend(["```", "", "## Noisy Feedback Case", "", "```json"])
    lines.append(
        json.dumps(
            {
                "normal_update": asdict(normal_update),
                "noisy_update": asdict(noisy_update),
                "noisy_feedback_conflict": noisy_update.feedback_conflict,
            },
            indent=2,
            sort_keys=True,
        )
    )
    lines.extend(["```", "", "## Conflicting Outcomes Case", "", "```json"])
    lines.append(json.dumps({key: asdict(value) for key, value in conflicting_bank.items()}, indent=2, sort_keys=True))
    lines.extend(["```", "", "## Multi-goal Arbitration Case", ""])
    selected_goal_id = multi_goal_result.selected_intention.goal_id if multi_goal_result.selected_intention else "none"
    lines.append(f"- Selected goal id: `{selected_goal_id}`")
    lines.append(f"- Selected intention: `{multi_goal_result.selected_intention.goal if multi_goal_result.selected_intention else 'none'}`")
    lines.extend(["", "| Rank | Goal | Goal ID | Priority | Affordance |", "|---:|---|---|---:|---|"])
    for row in build_priority_table(multi_goal_result):
        lines.append(
            f"| {row['rank']} | `{row['goal']}` | `{row['goal_id']}` | "
            f"{row['priority']} | `{row['affordance']}` |"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
