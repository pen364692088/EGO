"""Deterministic proposal-only desktop proto-life lab kernel.

This package is intentionally lab-only: it does not connect to LLMs, GUI
runtimes, system commands, external messaging, or user files.
"""

from ego_desktop_lab.gate import GateDecision, evaluate_gate
from ego_desktop_lab.intention import Intention, generate_intentions, select_intention
from ego_desktop_lab.affective_drive_loop import AffectiveDriveState, derive_affective_drive_state
from ego_desktop_lab.appraisal import AppraisalResult, appraise
from ego_desktop_lab.agency_decision_view import (
    AgencyDecisionView,
    build_agency_decision_view,
    format_agency_decision_view,
)
from ego_desktop_lab.agency_kernel import (
    SelfMaintainingAgencyCycleResult,
    run_self_maintaining_agency_cycle,
)
from ego_desktop_lab.agency_contracts import (
    AgencyEvent,
    BehaviorPlan,
    PerceptionFrame,
    build_behavior_plan,
    classify_feedback_text,
    derive_perception_frame,
)
from ego_desktop_lab.behavior_options import BehaviorOption
from ego_desktop_lab.belief_state import BeliefState
from ego_desktop_lab.decision_view import (
    DecisionView,
    build_decision_view_contract_report,
    build_decision_view_from_evidence_record,
    build_decision_view_from_semantic_result,
)
from ego_desktop_lab.experience_memory import (
    ExperienceBias,
    ExperienceCard,
    ExperienceContext,
    build_current_experience_context,
    build_experience_card,
    derive_experience_bias,
    resolve_experience_conflicts,
)
from ego_desktop_lab.motivation import MotivationState, update_motivation
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.root_cause import (
    FailureTicket,
    RootCauseTrace,
    build_operator_observability_report,
    build_root_cause_operator_report,
    build_root_cause_trace,
    diagnose_failure,
    format_failure_ticket,
)
from ego_desktop_lab.relational_companion import (
    CompanionSurfacePlan,
    DailyChatCorpusEvalResult,
    RelationalPreferenceState,
    RelationalSignal,
    RelationalSurfaceBias,
    apply_relational_surface_bias,
    build_companion_surface_plan,
    build_daily_chat_corpus_report,
    build_relational_preference_plasticity_report,
    build_relational_preference_state_from_feedback,
    classify_relational_intent,
    classify_relational_signal,
    derive_relational_surface_bias,
    evaluate_daily_chat_corpus,
    load_daily_chat_corpus,
)
from ego_desktop_lab.learning import LearningCycleResult, LearningUpdate, run_learning_cycle
from ego_desktop_lab.llm_adapter import (
    LLMCognitionAdapterResult,
    MockLLMAdapter,
    build_llm_cognition_adapter_report,
    build_llm_executive_proposal_report,
    parse_llm_json,
    run_llm_cognition_adapter,
)
from ego_desktop_lab.live_shadow_accuracy import (
    LiveShadowAccuracyCase,
    LiveShadowAccuracyObservation,
    build_live_llm_shadow_accuracy_report,
    build_live_shadow_accuracy_cases,
    build_live_shadow_accuracy_payload,
    run_live_shadow_accuracy_case,
)
from ego_desktop_lab.goal_reframe import GoalReframeProposal
from ego_desktop_lab.goal_operation import GoalOperationProposal, StructuredSubgoal
from ego_desktop_lab.goal_progress import FailureType, GoalProgressState, update_goal_progress
from ego_desktop_lab.oscillation import (
    OscillationConfig,
    OscillationControlCycleResult,
    build_oscillation_control_report,
    route_failure_type,
    run_oscillation_control_cycle,
    select_with_oscillation_control,
)
from ego_desktop_lab.pressure import MotivationPressure, derive_motivation_pressure
from ego_desktop_lab.semantic_proposal import ProposalValidationResult, SemanticProposal
from ego_desktop_lab.suggestion_renderer import SuggestionRenderResult, render_suggestion_from_canonical
from ego_desktop_lab.semantic_intelligence import (
    SemanticHandoff,
    SemanticScenario,
    SemanticScenarioResult,
    build_real_semantic_intelligence_report,
    build_semantic_policy_calibration_report,
    derive_validated_semantic_handoff,
    route_text_to_mock_scenario_id,
    run_semantic_scenario,
    run_semantic_text_event,
)
from ego_desktop_lab.semantic_provider import (
    LiveLLMShadowProvider,
    MockSemanticProvider,
    RuleSafetyPreRouter,
    SemanticProviderRequest,
    SemanticProviderResult,
    SemanticProviderSelection,
    select_semantic_provider_outputs,
)
from ego_desktop_lab.semantic_policy import (
    CanonicalDecision,
    SemanticPolicyCalibrationResult,
    SemanticPolicyOverlay,
    derive_semantic_policy_overlay,
    run_semantic_policy_calibration_cycle,
)
from ego_desktop_lab.plan_proposal import PlanProposal, PlanProposalSet
from ego_desktop_lab.explanation import ExplanationDraft
from ego_desktop_lab.stability import LearningConfig, build_stability_generalization_report
from ego_desktop_lab.strategy_memory import StrategyMemory
from ego_desktop_lab.reducer import AgentCycleResult, run_agent_cycle
from ego_desktop_lab.subject_state import Goal, SubjectState
from ego_desktop_lab.tension import Tension, detect_tensions

__all__ = [
    "AgentCycleResult",
    "AffectiveDriveState",
    "AgencyDecisionView",
    "AgencyEvent",
    "AppraisalResult",
    "BeliefState",
    "BehaviorOption",
    "BehaviorPlan",
    "CanonicalDecision",
    "CompanionSurfacePlan",
    "DailyChatCorpusEvalResult",
    "DecisionView",
    "GateDecision",
    "Goal",
    "GoalOperationProposal",
    "GoalReframeProposal",
    "GoalProgressState",
    "Intention",
    "FailureType",
    "FailureTicket",
    "LearningCycleResult",
    "LearningConfig",
    "LearningUpdate",
    "LLMCognitionAdapterResult",
    "LiveShadowAccuracyCase",
    "LiveShadowAccuracyObservation",
    "LiveLLMShadowProvider",
    "MockLLMAdapter",
    "MockSemanticProvider",
    "MotivationState",
    "MotivationPressure",
    "OscillationConfig",
    "OscillationControlCycleResult",
    "OutcomeRecord",
    "PlanProposal",
    "PlanProposalSet",
    "PerceptionFrame",
    "ProposalValidationResult",
    "RelationalPreferenceState",
    "RelationalSignal",
    "RelationalSurfaceBias",
    "RootCauseTrace",
    "SemanticHandoff",
    "SemanticProviderRequest",
    "SemanticProviderResult",
    "SemanticProviderSelection",
    "SemanticPolicyCalibrationResult",
    "SemanticPolicyOverlay",
    "ExplanationDraft",
    "ExperienceBias",
    "ExperienceCard",
    "ExperienceContext",
    "SemanticProposal",
    "SemanticScenario",
    "SemanticScenarioResult",
    "SelfMaintainingAgencyCycleResult",
    "SubjectState",
    "StrategyMemory",
    "StructuredSubgoal",
    "SuggestionRenderResult",
    "RuleSafetyPreRouter",
    "Tension",
    "appraise",
    "apply_relational_surface_bias",
    "build_oscillation_control_report",
    "build_operator_observability_report",
    "build_behavior_plan",
    "build_companion_surface_plan",
    "build_daily_chat_corpus_report",
    "build_relational_preference_plasticity_report",
    "build_relational_preference_state_from_feedback",
    "build_root_cause_operator_report",
    "build_root_cause_trace",
    "build_decision_view_contract_report",
    "build_decision_view_from_evidence_record",
    "build_decision_view_from_semantic_result",
    "build_current_experience_context",
    "build_experience_card",
    "build_llm_cognition_adapter_report",
    "build_llm_executive_proposal_report",
    "build_live_llm_shadow_accuracy_report",
    "build_live_shadow_accuracy_cases",
    "build_live_shadow_accuracy_payload",
    "build_agency_decision_view",
    "build_real_semantic_intelligence_report",
    "build_semantic_policy_calibration_report",
    "build_stability_generalization_report",
    "derive_semantic_policy_overlay",
    "derive_validated_semantic_handoff",
    "derive_motivation_pressure",
    "derive_experience_bias",
    "derive_affective_drive_state",
    "derive_perception_frame",
    "derive_relational_surface_bias",
    "classify_feedback_text",
    "classify_relational_intent",
    "classify_relational_signal",
    "diagnose_failure",
    "detect_tensions",
    "evaluate_gate",
    "evaluate_daily_chat_corpus",
    "format_agency_decision_view",
    "format_failure_ticket",
    "generate_intentions",
    "route_text_to_mock_scenario_id",
    "route_failure_type",
    "parse_llm_json",
    "run_learning_cycle",
    "run_live_shadow_accuracy_case",
    "run_agent_cycle",
    "run_llm_cognition_adapter",
    "run_oscillation_control_cycle",
    "run_semantic_policy_calibration_cycle",
    "run_semantic_scenario",
    "run_semantic_text_event",
    "run_self_maintaining_agency_cycle",
    "load_daily_chat_corpus",
    "select_intention",
    "select_semantic_provider_outputs",
    "select_with_oscillation_control",
    "render_suggestion_from_canonical",
    "resolve_experience_conflicts",
    "update_motivation",
    "update_goal_progress",
]
