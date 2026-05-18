from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ego_desktop_lab.appraisal import AppraisalResult
from ego_desktop_lab.belief_state import BeliefState
from ego_desktop_lab.gate import GateDecision
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.motivation import MotivationState
from ego_desktop_lab.pressure import MotivationPressure
from ego_desktop_lab.tension import Tension


@dataclass(frozen=True)
class EvidenceRecord:
    event_id: str
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
    timestamp: str
    previous_selected_intention: Intention | None = None
    outcome: Any | None = None
    learning_update: Any | None = None
    strategy_memory_before: dict[str, Any] | None = None
    strategy_memory_after: dict[str, Any] | None = None
    next_appraisal: AppraisalResult | None = None
    next_motivation_pressure: MotivationPressure | None = None
    next_affordance_pressure: dict[str, float] | None = None
    next_generated_intentions: tuple[Intention, ...] | None = None
    next_selected_intention: Intention | None = None
    feedback_conflict: bool | None = None
    goal_id: str | None = None
    goal_progress_before: Any | None = None
    goal_progress_after: Any | None = None
    failure_type: str | None = None
    oscillation_detected: bool | None = None
    hysteresis_decision: Any | None = None
    cooldown_decision: Any | None = None
    oscillation_selected_intention: Intention | None = None
    oscillation_reason: str | None = None
    reason: str | None = None
    llm_enabled: bool | None = None
    llm_raw_outputs: dict[str, str] | None = None
    semantic_proposal: Any | None = None
    plan_proposal: Any | None = None
    explanation_draft: Any | None = None
    proposal_validation_results: Any | None = None
    rejected_llm_proposals: Any | None = None
    llm_final_suggestion: str | None = None
    executive_semantic_proposal: Any | None = None
    executive_plan_proposals: Any | None = None
    executive_goal_reframe_proposal: Any | None = None
    executive_validation_results: Any | None = None
    executive_rejected_proposals: Any | None = None
    semantic_scenario_id: str | None = None
    semantic_scenario_text: str | None = None
    semantic_allowed_evidence_refs: tuple[str, ...] | None = None
    goal_operation_proposal: Any | None = None
    pending_goal_binding: bool | None = None
    semantic_handoff: Any | None = None
    next_core_cycle_influence: Any | None = None
    live_observation: Any | None = None
    semantic_provider_trace: Any | None = None
    semantic_shadow_outputs: dict[str, str] | None = None
    semantic_shadow_observation: Any | None = None
    accepted_failure_type: str | None = None
    canonical_decision: Any | None = None
    canonical_gate_decision: Any | None = None
    semantic_policy_overlay: Any | None = None
    before_pressure_map: dict[str, float] | None = None
    after_pressure_map: dict[str, float] | None = None
    before_selected_intention: Any | None = None
    after_selected_intention: Any | None = None
    selection_change_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def append_evidence_record(path: Path, record: EvidenceRecord) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    return path


def read_evidence_records(path: Path) -> tuple[dict[str, object], ...]:
    with path.open("r", encoding="utf-8") as handle:
        return tuple(json.loads(line) for line in handle if line.strip())
