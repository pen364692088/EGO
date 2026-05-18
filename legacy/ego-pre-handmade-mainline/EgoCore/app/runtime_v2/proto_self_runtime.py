from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import logging
import os

from openemotion.proto_self_v2.seed_schemas import SEED_SCHEMA_VERSION, SEED_SUBJECT_PROFILE
from openemotion.embodied_self import (
    REQUIRED_WRITEBACK_GATE as EMBODIED_WRITEBACK_GATE,
    BoundaryPressureMode as EmbodiedBoundaryPressureMode,
    EmbodiedProposalStatus,
    EmbodiedSelfOwner,
    EmbodiedSelfState,
    EmbodiedSelfStore,
    EnvironmentCouplingStatus,
)
from openemotion.initiative_self import (
    REQUIRED_WRITEBACK_GATE as INITIATIVE_WRITEBACK_GATE,
    CommitmentContinuityStatus as InitiativeCommitmentContinuityStatus,
    HostProactiveCandidateStatus,
    InitiativePriority,
    InitiativeProposalStatus,
    InitiativeSelfOwner,
    InitiativeSelfState,
    InitiativeSelfStore,
)
from openemotion.initiative_realization import (
    REQUIRED_WRITEBACK_GATE as INITIATIVE_REALIZATION_WRITEBACK_GATE,
    CommitmentFulfillmentStatus,
    ControlledDeliveryCandidateStatus,
    InitiativeRealizationOwner,
    InitiativeRealizationState,
    InitiativeRealizationStore,
    RealizationMode,
    RealizationProposalStatus,
)
from openemotion.developmental_self import (
    REQUIRED_WRITEBACK_GATE as DEVELOPMENTAL_WRITEBACK_GATE,
    ContinuityMarkerType,
    DevelopmentalSelfOwner,
    DevelopmentalSelfState,
    DevelopmentalSelfStore,
    PromotionLevel,
    compact_developmental_self_context,
)
from openemotion.endogenous_drives import EndogenousDriveStore, EndogenousDriveOwner, compact_endogenous_drive_context
from openemotion.endogenous_drives.reducers import seed_default_state
from openemotion.reflective_self import (
    ReflectiveSelfOwner,
    ReflectiveSelfState,
    ReflectiveSelfStore,
    ReflectionTargetType,
)
from openemotion.selfhood_integration import (
    REQUIRED_WRITEBACK_GATE as SELFHOOD_INTEGRATION_WRITEBACK_GATE,
    ArbitrationPriority as SelfhoodArbitrationPriority,
    ConflictSeverity as SelfhoodConflictSeverity,
    IntegratedProposalStatus as SelfhoodIntegratedProposalStatus,
    SelfhoodIntegrationOwner,
    SelfhoodIntegrationState,
    SelfhoodIntegrationStore,
)
from openemotion.social_self import (
    REQUIRED_WRITEBACK_GATE as SOCIAL_WRITEBACK_GATE,
    BoundaryMode as SocialBoundaryMode,
    CommitmentStatus as SocialCommitmentStatus,
    RelationshipContinuityStatus,
    RepairProposalStatus as SocialRepairProposalStatus,
    SocialSelfOwner,
    SocialSelfState,
    SocialSelfStore,
)
from openemotion.self_model import (
    PHASE1_AUTHORITATIVE_FIELDS,
    SelfModelStore,
    SelfModelUpdateRequest,
    apply_governed_writeback,
    create_default_self_model,
)

from app.risk_signal import (
    assess_message_risk_level,
    risk_level_from_external_result,
)
from .state import RuntimeV2State

logger = logging.getLogger(__name__)
ENABLE_MVP12_SANDBOX = os.environ.get("EGO_ENABLE_MVP12_SANDBOX", "false").lower() == "true"
H1_CANONICAL_SHADOW_ENV = "EGO_ENABLE_H1_CANONICAL_SHADOW"
H1_CANONICAL_SHADOW_ALLOWLIST_ENV = "EGO_H1_CANONICAL_SHADOW_ALLOWLIST"
H1_CANONICAL_SHADOW_RUNTIME_FIELD = "h1_canonical_shadow"
DEFAULT_SELF_MODEL_IDENTITY_HANDLE = "openemotion"
DEFAULT_ENDOGENOUS_DRIVE_IDENTITY_HANDLE = "openemotion"
DEFAULT_REFLECTIVE_SELF_IDENTITY_HANDLE = "openemotion"
DEFAULT_DEVELOPMENTAL_SELF_IDENTITY_HANDLE = "openemotion"
DEFAULT_SOCIAL_SELF_IDENTITY_HANDLE = "openemotion"
DEFAULT_EMBODIED_SELF_IDENTITY_HANDLE = "openemotion"
DEFAULT_SELFHOOD_INTEGRATION_IDENTITY_HANDLE = "openemotion"
DEFAULT_INITIATIVE_SELF_IDENTITY_HANDLE = "openemotion"
DEFAULT_INITIATIVE_REALIZATION_IDENTITY_HANDLE = "openemotion"
def assess_risk_level(user_input: str) -> str:
    return assess_message_risk_level(user_input)


def resolve_proto_self_schema_version(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    if ingress_context.get("proto_self_version") == "v1":
        return "proto_self.v1"
    return "proto_self.v2"


def resolve_proto_self_subject_profile(state: RuntimeV2State) -> Optional[str]:
    ingress_context = state.ingress_context or {}
    subject_profile = ingress_context.get("proto_self_subject_profile")
    if subject_profile:
        return str(subject_profile)
    return state.proto_self_subject_profile_override


def _resolved_target(state: RuntimeV2State) -> Dict[str, Any]:
    return dict(((state.ingress_context or {}).get("resolved_target") or {}))


def _proto_self_state_scope_context(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    state_scope = str(
        ingress_context.get("proto_self_state_scope")
        or ingress_context.get("state_scope")
        or "agent_global"
    ).strip() or "agent_global"
    experiment_id = str(
        ingress_context.get("proto_self_experiment_id")
        or ingress_context.get("experiment_id")
        or ""
    ).strip() or None
    context = {"state_scope": state_scope}
    if state_scope == "experiment" and experiment_id:
        context["experiment_id"] = experiment_id
    return context


def _inject_private_research_runtime_summary_overrides(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    overrides = dict(ingress_context.get("proto_self_runtime_summary_overrides") or {})
    if not overrides:
        return runtime_summary

    updated = dict(runtime_summary or {})

    raw_mvs_replay = overrides.get("mvs_replay")
    if isinstance(raw_mvs_replay, dict):
        mvs_replay: Dict[str, Any] = {}
        if raw_mvs_replay.get("enabled") is not None:
            mvs_replay["enabled"] = bool(raw_mvs_replay.get("enabled"))
        if raw_mvs_replay.get("shadow_only") is not None:
            mvs_replay["shadow_only"] = bool(raw_mvs_replay.get("shadow_only"))
        for key in (
            "variant_id",
            "action_family",
            "family",
            "case_id",
            "step_id",
            "source_type",
            "slice_id",
            "scenario_id",
            "segment_id",
        ):
            value = raw_mvs_replay.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                mvs_replay[key] = text
        if mvs_replay:
            updated["mvs_replay"] = mvs_replay

    raw_controlled_observation = overrides.get("controlled_observation")
    if isinstance(raw_controlled_observation, dict):
        controlled_observation: Dict[str, Any] = {}
        if raw_controlled_observation.get("enabled") is not None:
            controlled_observation["enabled"] = bool(raw_controlled_observation.get("enabled"))
        if raw_controlled_observation.get("shadow_only") is not None:
            controlled_observation["shadow_only"] = bool(raw_controlled_observation.get("shadow_only"))
        for key in (
            "trial_id",
            "scenario_id",
            "family",
            "source_type",
            "segment_id",
            "state_snapshot_ref",
        ):
            value = raw_controlled_observation.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                controlled_observation[key] = text
        if controlled_observation:
            updated["controlled_observation"] = controlled_observation

    return updated


def _inject_private_proto_self_safety_overrides(
    safety_context: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    raw_overrides = dict(ingress_context.get("proto_self_safety_context_overrides") or {})
    if not raw_overrides:
        return safety_context

    updated = dict(safety_context or {})
    risk_level = raw_overrides.get("risk_level")
    if risk_level is not None:
        normalized = str(risk_level).strip().lower()
        if normalized in {"low", "medium", "high", "critical"}:
            updated["risk_level"] = normalized

    if raw_overrides.get("boundary_touched") is not None:
        updated["boundary_touched"] = bool(raw_overrides.get("boundary_touched"))

    return updated


def _seed_runtime_summary(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    resolved_target = _resolved_target(state)
    summary = {
        "runtime": "runtime_v2",
        "runtime_action": ingress_context.get("runtime_action"),
        "request_mode": ingress_context.get("request_mode"),
        "interaction_kind": ingress_context.get("interaction_kind"),
        "conversation_act": ingress_context.get("conversation_act"),
        "parser_source": ingress_context.get("parser_source"),
        "primary_intent": ingress_context.get("primary_intent"),
        "active_task": state.task_status in {"running", "waiting_input", "resumable_pause"},
        "confirm_pending": bool(ingress_context.get("confirm_pending")),
        "clarification_needed": bool(ingress_context.get("requires_clarification")),
        "pending_commitment": state.current_goal,
        "resolved_target_path": resolved_target.get("path"),
        "resolved_target_name": resolved_target.get("filename") or resolved_target.get("artifact_id"),
        "recent_failure_target": (
            resolved_target.get("path")
            if state.last_tool_result and not state.last_tool_result.get("success")
            else None
        ),
        "browser_tabs": list(ingress_context.get("browser_tabs") or []),
        "idle_window": _build_idle_window(state),
        "recent_delivery_outcome": _build_recent_delivery_outcome(state),
        "resource_budget_hint": _build_resource_budget_hint(state),
        "maintenance_context": _build_maintenance_context(state),
    }
    summary.update(_proto_self_state_scope_context(state))
    summary = _inject_private_research_runtime_summary_overrides(summary, state=state)
    return _inject_h1_canonical_shadow_context(summary, state=state)


def _h1_canonical_shadow_enabled() -> bool:
    return os.environ.get(H1_CANONICAL_SHADOW_ENV, "false").strip().lower() == "true"


def _parse_h1_canonical_shadow_allowlist() -> set[str]:
    raw = os.environ.get(H1_CANONICAL_SHADOW_ALLOWLIST_ENV, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _is_h1_canonical_shadow_allowlisted(state: RuntimeV2State) -> bool:
    allowlist = _parse_h1_canonical_shadow_allowlist()
    if not allowlist:
        return True
    ingress_context = state.ingress_context or {}
    candidates = {
        str(getattr(state, "session_id", "") or ""),
        str(getattr(state, "active_turn_id", "") or ""),
        str(ingress_context.get("capture_id") or ""),
        str(ingress_context.get("observation_source") or ""),
    }
    return "*" in allowlist or bool(allowlist & {item for item in candidates if item})


def _inject_h1_canonical_shadow_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    if not _h1_canonical_shadow_enabled():
        return runtime_summary
    updated = dict(runtime_summary or {})
    allowlisted = _is_h1_canonical_shadow_allowlisted(state)
    updated[H1_CANONICAL_SHADOW_RUNTIME_FIELD] = {
        "enabled": allowlisted,
        "shadow_only": True,
        "allowlisted": allowlisted,
        "source": "canonical_shadow",
        "rollout_owner": "egocore.runtime_v2",
    }
    return updated


def _extract_shadow_h1_telemetry(proto_self_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    trace_payload = dict(proto_self_result.get("trace_payload") or {})
    legacy_trace_payload = dict(trace_payload.get("legacy_trace_payload") or {})
    raw = trace_payload.get("shadow_h1") or legacy_trace_payload.get("shadow_h1")
    if not isinstance(raw, dict) or not raw:
        confidence_meta = dict(proto_self_result.get("confidence_meta") or {})
        if not confidence_meta.get("shadow_h1_enabled"):
            return None
        raw = {
            "enabled": True,
            "action_key": confidence_meta.get("shadow_h1_action_key"),
            "predicted_success": confidence_meta.get("shadow_h1_predicted_success"),
            "threshold": confidence_meta.get("shadow_h1_threshold"),
            "would_guard": confidence_meta.get("shadow_h1_would_guard"),
            "would_ask": confidence_meta.get("shadow_h1_would_ask"),
            "source": "canonical_shadow",
        }
    return {
        "enabled": bool(raw.get("enabled")),
        "action_key": str(raw.get("action_key") or ""),
        "predicted_success": float(raw.get("predicted_success") or 0.0),
        "threshold": float(raw.get("threshold") or 0.0),
        "would_guard": bool(raw.get("would_guard")),
        "would_ask": bool(raw.get("would_ask")),
        "source": str(raw.get("source") or "canonical_shadow"),
    }


def _update_shadow_h1_proto_self_context(
    state: RuntimeV2State,
    proto_self_result: Dict[str, Any],
    *,
    preserve_existing: bool = False,
) -> None:
    if state.proto_self_context is None:
        state.proto_self_context = {}
    shadow_h1 = _extract_shadow_h1_telemetry(proto_self_result)
    if shadow_h1 is not None:
        state.proto_self_context["shadow_h1"] = shadow_h1
    elif not preserve_existing:
        state.proto_self_context.pop("shadow_h1", None)


def _resolve_self_model_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("self_model_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_SELF_MODEL_IDENTITY_HANDLE
    )


def _resolve_endogenous_drive_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("endogenous_drive_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_ENDOGENOUS_DRIVE_IDENTITY_HANDLE
    )


def _resolve_reflective_self_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("reflective_self_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_REFLECTIVE_SELF_IDENTITY_HANDLE
    )


def _resolve_developmental_self_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("developmental_self_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_DEVELOPMENTAL_SELF_IDENTITY_HANDLE
    )


def _resolve_social_self_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("social_self_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_SOCIAL_SELF_IDENTITY_HANDLE
    )


def _resolve_embodied_self_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("embodied_self_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_EMBODIED_SELF_IDENTITY_HANDLE
    )


def _resolve_selfhood_integration_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("selfhood_integration_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_SELFHOOD_INTEGRATION_IDENTITY_HANDLE
    )


def _resolve_initiative_self_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("initiative_self_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_INITIATIVE_SELF_IDENTITY_HANDLE
    )


def _resolve_initiative_realization_identity_handle(state: RuntimeV2State) -> str:
    ingress_context = state.ingress_context or {}
    return str(
        ingress_context.get("initiative_realization_identity_handle")
        or ingress_context.get("identity_handle")
        or DEFAULT_INITIATIVE_REALIZATION_IDENTITY_HANDLE
    )


def _build_idle_window(state: RuntimeV2State) -> Dict[str, Any]:
    return {
        "idle_seconds": round(state.idle_seconds_since_chat_activity(), 3),
        "active_turn_status": state.active_turn_status,
        "task_status": state.task_status,
    }


def _build_recent_delivery_outcome(state: RuntimeV2State) -> Dict[str, Any]:
    outcome: Dict[str, Any] = {
        "delivery_type": state.last_delivery_type,
        "final_sent": state.final_sent,
        "active_turn_terminal": state.active_turn_status == "terminal",
    }
    if state.last_tool_result:
        outcome.update(
            {
                "kind": "tool",
                "success": bool(state.last_tool_result.get("success")),
                "status": "success" if state.last_tool_result.get("success") else "failed",
                "tool": state.last_tool_result.get("tool"),
            }
        )
    else:
        outcome.setdefault("kind", "chat")
        if state.final_sent:
            outcome.setdefault("success", True)
            outcome.setdefault("status", "sent")
    return outcome


_RICH_SUBJECT_SURFACE_FIELDS = (
    "social_policy_hints",
    "embodied_policy_hints",
    "integrated_policy_hints",
    "initiative_policy_hints",
)

_RICH_TRACE_CONTEXT_FIELDS = (
    "social_context",
    "environment_context",
    "selfhood_integration_context",
    "initiative_realization_context",
    "host_proactive_context",
)


def normalize_chat_subject_surface(proto_self_result: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(proto_self_result or {})
    for field in _RICH_SUBJECT_SURFACE_FIELDS:
        normalized[field] = dict(normalized.get(field) or {})

    trace_payload = normalized.get("trace_payload")
    if isinstance(trace_payload, dict):
        normalized_trace_payload = dict(trace_payload)
        for field in _RICH_TRACE_CONTEXT_FIELDS:
            normalized_trace_payload[field] = dict(normalized_trace_payload.get(field) or {})
        normalized["trace_payload"] = normalized_trace_payload

    return normalized


def _build_resource_budget_hint(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    if ingress_context.get("resource_budget_hint"):
        return dict(ingress_context.get("resource_budget_hint") or {})
    reserve_level = "low" if state.task_status in {"running", "blocked"} else "normal"
    return {
        "reserve_level": reserve_level,
        "active_task": state.task_status in {"running", "waiting_input", "resumable_pause", "blocked"},
        "waiting_for_user_input": state.waiting_for_user_input,
    }


def _build_maintenance_context(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    maintenance_context = dict(ingress_context.get("maintenance_context") or {})
    proto_self_context = dict(state.proto_self_context or {})
    if "shadow_revision" in proto_self_context:
        maintenance_context.setdefault("shadow_revision", proto_self_context.get("shadow_revision"))
    if "background_thought_candidates" in proto_self_context:
        maintenance_context.setdefault(
            "background_thought_candidate_count",
            len(proto_self_context.get("background_thought_candidates") or []),
        )
    return maintenance_context


def _build_developmental_context(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    provided = dict(ingress_context.get("developmental_context") or {})
    proto_self_context = dict(state.proto_self_context or {})
    maintenance_context = _build_maintenance_context(state)

    context: Dict[str, Any] = {
        "source": str(provided.get("source") or "runtime_v2"),
    }

    if "continuity_gap" in provided:
        context["continuity_gap"] = float(provided.get("continuity_gap") or 0.0)
    else:
        continuity_snapshot = dict(proto_self_context.get("developmental_continuity_snapshot") or {})
        if "continuity_gap" in continuity_snapshot:
            context["continuity_gap"] = float(continuity_snapshot.get("continuity_gap") or 0.0)
        elif proto_self_context.get("shadow_revision") is not None:
            candidate_count = len(proto_self_context.get("background_thought_candidates") or [])
            context["continuity_gap"] = round(min(1.0, 0.15 + (candidate_count * 0.05)), 3)
        elif state.last_tool_result and not state.last_tool_result.get("success"):
            context["continuity_gap"] = 0.2

    if "growth_pressure_hint" in provided:
        context["growth_pressure_hint"] = float(provided.get("growth_pressure_hint") or 0.0)
    else:
        candidate_bias_terms = dict(proto_self_context.get("candidate_bias_terms") or {})
        completion_bias = float(candidate_bias_terms.get("completion") or 0.0)
        exploration_bias = float(candidate_bias_terms.get("exploration") or 0.0)
        if completion_bias or exploration_bias:
            context["growth_pressure_hint"] = round(min(1.0, max(completion_bias, exploration_bias)), 3)
        elif state.current_goal:
            context["growth_pressure_hint"] = 0.35

    if "stagnation_signal_hint" in provided:
        context["stagnation_signal_hint"] = float(provided.get("stagnation_signal_hint") or 0.0)
    else:
        if state.waiting_for_user_input or state.task_status in {"blocked", "waiting_input", "resumable_pause"}:
            context["stagnation_signal_hint"] = 0.4
        elif maintenance_context.get("background_thought_candidate_count"):
            context["stagnation_signal_hint"] = 0.25

    context["identity_guard"] = str(
        provided.get("identity_guard")
        or ingress_context.get("identity_guard_mode")
        or "bounded"
    )

    if "replay_debt" in provided:
        context["replay_debt"] = float(provided.get("replay_debt") or 0.0)
    else:
        context["replay_debt"] = 0.2 if state.last_tool_result and not state.last_tool_result.get("success") else 0.0

    context["promotion_budget"] = str(
        provided.get("promotion_budget")
        or ("review_only" if state.current_goal else "shadow_only")
    )

    if "drift_markers" in provided:
        context["drift_markers"] = list(provided.get("drift_markers") or [])
    else:
        drift_markers = []
        if state.last_tool_result and not state.last_tool_result.get("success"):
            drift_markers.append("recent_delivery_failure")
        if proto_self_context.get("shadow_revision") is not None:
            drift_markers.append("developmental_shadow_present")
        if state.waiting_for_user_input:
            drift_markers.append("waiting_for_user_input")
        context["drift_markers"] = drift_markers

    return context


def _build_social_context(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    provided = dict(ingress_context.get("social_context") or {})
    relationship_context = dict(state.get_chat_state().relationship_context or {})

    social_arc = str(relationship_context.get("current_social_arc") or "").strip().lower()
    continuity_by_arc = {
        "warming": "stable",
        "stable": "stable",
        "cooling": "strained",
        "repairing": "repairing",
        "testing": "strained",
        "unknown": "stable",
    }

    conversation_temperature = float(relationship_context.get("conversation_temperature") or 0.5)
    if conversation_temperature <= 0.35:
        trust_drift = -0.25
    elif conversation_temperature < 0.5:
        trust_drift = -0.1
    elif conversation_temperature >= 0.75:
        trust_drift = 0.12
    elif conversation_temperature >= 0.6:
        trust_drift = 0.06
    else:
        trust_drift = 0.0

    repair_state = str(relationship_context.get("last_repair_state") or "").strip().lower()
    repair_outcome = str(provided.get("repair_outcome") or "").strip()
    if not repair_outcome:
        if state.last_tool_result and not state.last_tool_result.get("success") and repair_state in {"needed", "in_progress"}:
            repair_outcome = "blocked"
        elif repair_state == "resolved":
            repair_outcome = "resolved"

    boundary_signal = str(provided.get("boundary_signal") or "").strip()
    if not boundary_signal:
        if relationship_context.get("last_user_feedback_about_tone") or conversation_temperature < 0.4:
            boundary_signal = "cautious"
        else:
            boundary_signal = "open"

    commitment_event = str(provided.get("commitment_event") or "").strip()
    if not commitment_event and state.current_goal and state.task_status in {"waiting_input", "resumable_pause"}:
        commitment_event = "held"

    unresolved_repair = bool(provided.get("unresolved_repair"))
    if not unresolved_repair:
        unresolved_repair = repair_state in {"needed", "in_progress"} or repair_outcome in {"blocked", "failed"}

    return {
        "source": str(provided.get("source") or "runtime_v2"),
        "counterpart_id": str(
            provided.get("counterpart_id")
            or ingress_context.get("counterpart_id")
            or state.session_id
        ),
        "relationship_event": str(
            provided.get("relationship_event")
            or state.get_chat_state().last_chat_act
            or relationship_context.get("last_relationship_shift")
            or ""
        ),
        "relationship_continuity": str(
            provided.get("relationship_continuity")
            or continuity_by_arc.get(social_arc, "stable")
        ),
        "trust_drift": float(provided.get("trust_drift") if "trust_drift" in provided else trust_drift),
        "commitment_event": commitment_event,
        "commitment_breach": bool(provided.get("commitment_breach")),
        "repair_outcome": repair_outcome,
        "unresolved_repair": unresolved_repair,
        "boundary_signal": boundary_signal,
        "promotion_budget": str(provided.get("promotion_budget") or "review_only"),
    }


def _build_environment_context(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    provided = dict(ingress_context.get("environment_context") or {})
    resource_budget_hint = _build_resource_budget_hint(state)
    delivery_outcome = _build_recent_delivery_outcome(state)

    reserve_level = str(resource_budget_hint.get("reserve_level") or "normal").strip().lower()
    delivery_status = str(delivery_outcome.get("status") or "").strip().lower()
    risk_level = str(
        ingress_context.get("risk_level")
        or delivery_outcome.get("risk_level")
        or "low"
    ).strip().lower()

    if "resource_pressure_hint" in provided:
        resource_pressure_hint = float(provided.get("resource_pressure_hint") or 0.0)
    else:
        resource_pressure_hint = {
            "low": 0.78,
            "normal": 0.45,
        }.get(reserve_level, 0.45)
        if delivery_status in {"failed", "blocked"}:
            resource_pressure_hint = max(resource_pressure_hint, 0.72)

    if "slack_hint" in provided:
        slack_hint = float(provided.get("slack_hint") or 0.0)
    else:
        slack_hint = {
            "low": 0.22,
            "normal": 0.52,
        }.get(reserve_level, 0.52)
        if delivery_status in {"failed", "blocked"}:
            slack_hint = min(slack_hint, 0.3)

    if "boundary_pressure_hint" in provided:
        boundary_pressure_hint = float(provided.get("boundary_pressure_hint") or 0.0)
    else:
        boundary_pressure_hint = 0.22
        if state.last_tool_result and not state.last_tool_result.get("success"):
            boundary_pressure_hint = max(boundary_pressure_hint, 0.58)
        if risk_level in {"critical", "high"}:
            boundary_pressure_hint = max(boundary_pressure_hint, 0.66)

    if "boundary_signal" in provided:
        boundary_signal = str(provided.get("boundary_signal") or "")
    else:
        if risk_level == "critical":
            boundary_signal = "repair_only"
        elif boundary_pressure_hint >= 0.55 or delivery_status in {"failed", "blocked"}:
            boundary_signal = "guarded"
        else:
            boundary_signal = "open"

    if "stabilization_needed" in provided:
        stabilization_needed = bool(provided.get("stabilization_needed"))
    else:
        stabilization_needed = bool(
            (state.last_tool_result and not state.last_tool_result.get("success"))
            or delivery_status in {"failed", "blocked"}
            or boundary_pressure_hint >= 0.55
            or resource_pressure_hint >= 0.7
        )

    action_ref = str(provided.get("action_ref") or "").strip()
    if not action_ref and state.last_tool_result:
        tool_name = str(state.last_tool_result.get("tool") or "tool")
        turn_id = state.last_tool_result_turn_id or state.active_turn_id or "unknown"
        action_ref = f"{tool_name}:{turn_id}"
    elif not action_ref and state.current_goal:
        action_ref = f"goal:{state.current_goal}"

    coupling_event = str(provided.get("coupling_event") or "").strip()
    if not coupling_event:
        if state.last_tool_result:
            coupling_event = "tool_result"
        elif state.final_sent:
            coupling_event = "delivery_result"
        else:
            coupling_event = "runtime_observe"

    outcome_type = str(provided.get("outcome_type") or "").strip()
    if not outcome_type:
        if state.last_tool_result:
            outcome_type = "failure" if not state.last_tool_result.get("success") else "success"
        else:
            outcome_type = delivery_status or "observed"

    outcome_summary = str(provided.get("outcome_summary") or "").strip()
    if not outcome_summary:
        if state.last_tool_result:
            tool_name = str(state.last_tool_result.get("tool") or "tool")
            if state.last_tool_result.get("success"):
                outcome_summary = f"{tool_name} completed under runtime_v2"
            else:
                outcome_summary = f"{tool_name} failure increased embodied pressure"
        else:
            outcome_summary = f"runtime delivery status: {delivery_status or 'observed'}"

    promotion_budget = str(
        provided.get("promotion_budget")
        or ("review_only" if stabilization_needed or state.current_goal else "shadow_only")
    )

    return {
        "source": str(provided.get("source") or "runtime_v2"),
        "action_ref": action_ref,
        "coupling_event": coupling_event,
        "outcome_type": outcome_type,
        "outcome_summary": outcome_summary,
        "resource_pressure_hint": resource_pressure_hint,
        "slack_hint": slack_hint,
        "boundary_signal": boundary_signal,
        "boundary_pressure_hint": boundary_pressure_hint,
        "stabilization_needed": stabilization_needed,
        "promotion_budget": promotion_budget,
    }


def _build_initiative_context(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    provided = dict(ingress_context.get("initiative_context") or {})
    proto_self_context = dict(state.proto_self_context or {})
    resource_budget_hint = _build_resource_budget_hint(state)
    delivery_outcome = _build_recent_delivery_outcome(state)
    idle_window = _build_idle_window(state)
    integration_snapshot = dict(proto_self_context.get("cross_axis_priority_snapshot") or {})
    selected_priority = str(
        integration_snapshot.get("selected_priority")
        or (proto_self_context.get("integrated_policy_hints") or {}).get("integrated_priority")
        or ""
    ).strip()

    pending_commitment_refs = list(provided.get("pending_commitment_refs") or [])
    if not pending_commitment_refs and state.current_goal:
        pending_commitment_refs = [f"goal:{state.current_goal}"]
    blocked_commitment_refs = list(provided.get("blocked_commitment_refs") or [])
    if not blocked_commitment_refs and state.task_status == "blocked" and state.current_goal:
        blocked_commitment_refs = [f"goal:{state.current_goal}"]

    initiative_trigger = str(provided.get("initiative_trigger") or "").strip()
    if not initiative_trigger:
        if state.current_goal and idle_window.get("idle_seconds", 0.0) >= 600.0:
            initiative_trigger = "commitment_followup"
        elif delivery_outcome.get("status") in {"failed", "blocked"}:
            initiative_trigger = "delivery_repair_review"
        elif selected_priority:
            initiative_trigger = f"integration_{selected_priority}"
        else:
            initiative_trigger = "runtime_review"

    continuity_ref = str(provided.get("continuity_ref") or "").strip()
    if not continuity_ref and pending_commitment_refs:
        continuity_ref = str(pending_commitment_refs[0])
    elif not continuity_ref and blocked_commitment_refs:
        continuity_ref = str(blocked_commitment_refs[0])

    host_lane_hint = str(provided.get("host_lane_hint") or "").strip()
    if not host_lane_hint:
        host_lane_hint = "host_proactive_outbox"

    promotion_budget = str(provided.get("promotion_budget") or "").strip()
    if not promotion_budget:
        promotion_budget = "review_only" if selected_priority in {"review", "guard", "stabilize"} else "controlled_axis"

    return {
        "source": str(provided.get("source") or "runtime_v2"),
        "initiative_trigger": initiative_trigger,
        "continuity_ref": continuity_ref,
        "pending_commitment_refs": pending_commitment_refs,
        "blocked_commitment_refs": blocked_commitment_refs,
        "reserve_level": str(provided.get("reserve_level") or resource_budget_hint.get("reserve_level") or "normal"),
        "recent_delivery_status": str(
            provided.get("recent_delivery_status")
            or delivery_outcome.get("status")
            or ("sent" if delivery_outcome.get("success") else "")
        ),
        "delivery_failure": bool(provided.get("delivery_failure"))
        or delivery_outcome.get("status") in {"failed", "blocked"}
        or delivery_outcome.get("success") is False,
        "idle_seconds": float(provided.get("idle_seconds") or idle_window.get("idle_seconds") or 0.0),
        "host_lane_hint": host_lane_hint,
        "promotion_budget": promotion_budget,
    }


def _build_host_proactive_context(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    provided = dict(ingress_context.get("host_proactive_context") or {})
    initiative_context = _build_initiative_context(state)
    proto_self_context = dict(state.proto_self_context or {})
    commitment_snapshot = dict(proto_self_context.get("commitment_execution_snapshot") or {})
    initiative_policy_hints = dict(proto_self_context.get("initiative_policy_hints") or {})
    host_candidate = dict(proto_self_context.get("host_proactive_candidate") or {})
    recent_delivery = _build_recent_delivery_outcome(state)
    resource_budget = _build_resource_budget_hint(state)

    host_lane_hints = list(provided.get("host_lane_hints") or host_candidate.get("host_lane_hints") or [])
    host_lane_hint = str(
        provided.get("host_lane_hint")
        or host_candidate.get("host_lane_hint")
        or initiative_context.get("host_lane_hint")
        or "host_proactive_outbox"
    )
    if host_lane_hint and host_lane_hint not in host_lane_hints:
        host_lane_hints.insert(0, host_lane_hint)

    pending_realization_refs = list(
        provided.get("pending_realization_refs")
        or commitment_snapshot.get("carried_commitment_refs")
        or initiative_context.get("pending_commitment_refs")
        or []
    )
    readiness_basis = str(
        provided.get("readiness_basis")
        or host_candidate.get("continuity_basis")
        or commitment_snapshot.get("commitment_mode")
        or initiative_context.get("initiative_trigger")
        or "bounded_commitment_followup"
    )
    delivery_readiness = provided.get("delivery_readiness")
    if delivery_readiness is None:
        delivery_readiness = host_candidate.get("delivery_readiness")
    if delivery_readiness is None:
        delivery_readiness = commitment_snapshot.get("continuity_confidence")
    if delivery_readiness is None:
        delivery_readiness = 0.0

    return {
        "source": str(provided.get("source") or "runtime_v2"),
        "host_lane_hints": host_lane_hints,
        "delivery_readiness": float(delivery_readiness or 0.0),
        "readiness_basis": readiness_basis,
        "host_lane_hint": host_lane_hint,
        "reserve_level_hint": str(
            provided.get("reserve_level_hint")
            or resource_budget.get("reserve_level")
            or initiative_context.get("reserve_level")
            or ""
        ),
        "pending_realization_refs": pending_realization_refs,
        "recent_delivery_success": bool(
            provided.get("recent_delivery_success")
            if "recent_delivery_success" in provided
            else recent_delivery.get("success")
        ),
        "recent_delivery_status": str(
            provided.get("recent_delivery_status")
            or recent_delivery.get("status")
            or initiative_context.get("recent_delivery_status")
            or ""
        ),
        "promotion_budget": str(
            provided.get("promotion_budget")
            or host_candidate.get("promotion_level")
            or initiative_context.get("promotion_budget")
            or "review_only"
        ),
    }


def _compact_self_model_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    context: Dict[str, Any] = {}
    for field_name in PHASE1_AUTHORITATIVE_FIELDS:
        if field_name not in snapshot:
            continue
        value = snapshot[field_name]
        if field_name == "modification_audit_trail":
            context[field_name] = list(value or [])[-5:]
            continue
        context[field_name] = value
    return context


def _inject_self_model_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    self_model_store: Optional[SelfModelStore] = None,
) -> Dict[str, Any]:
    store = self_model_store or SelfModelStore()
    identity_handle = _resolve_self_model_identity_handle(state)
    snapshot = store.load_snapshot(identity_handle)
    source = "loaded" if snapshot else "missing"
    if not snapshot:
        try:
            store.save(
                create_default_self_model(identity_handle),
                update_source="owner_bootstrap_live",
                trace_reference="runtime_v2:self_model_bootstrap",
                confidence_class="high",
            )
            snapshot = store.load_snapshot(identity_handle)
            source = "bootstrapped_live" if snapshot else "bootstrap_failed"
            if snapshot:
                logger.info(
                    "runtime_v2.self_model_bootstrap identity_handle=%s store_path=%s source=%s",
                    identity_handle,
                    store.state_file(identity_handle),
                    source,
                )
            else:
                logger.error(
                    "runtime_v2.self_model_bootstrap_failed identity_handle=%s store_path=%s reason=no_snapshot_after_save",
                    identity_handle,
                    store.state_file(identity_handle),
                )
        except Exception:
            source = "bootstrap_failed"
            logger.exception(
                "runtime_v2.self_model_bootstrap_failed identity_handle=%s store_path=%s",
                identity_handle,
                store.state_file(identity_handle),
            )
    runtime_summary["self_model_context_source"] = source
    if snapshot:
        runtime_summary["self_model_context"] = _compact_self_model_context(snapshot)
    return runtime_summary


def _inject_endogenous_drive_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    endogenous_drive_store: Optional[EndogenousDriveStore] = None,
) -> Dict[str, Any]:
    store = endogenous_drive_store or EndogenousDriveStore()
    snapshot = store.load_snapshot(_resolve_endogenous_drive_identity_handle(state))
    if snapshot:
        runtime_summary["endogenous_drive_context"] = compact_endogenous_drive_context(snapshot)
    return runtime_summary


def _compact_reflective_self_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = ReflectiveSelfState.model_validate(snapshot)
    return {
        "schema_version": state.schema_version,
        "owner_revision": state.owner_revision,
        "last_revision_id": state.last_revision_id,
        **state.to_runtime_projection(),
    }


def _inject_reflective_self_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    reflective_self_store: Optional[ReflectiveSelfStore] = None,
) -> Dict[str, Any]:
    store = reflective_self_store or ReflectiveSelfStore()
    snapshot = store.load_snapshot(_resolve_reflective_self_identity_handle(state))
    if snapshot:
        runtime_summary["reflective_self_context"] = _compact_reflective_self_context(snapshot)
    return runtime_summary


def _compact_developmental_self_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = DevelopmentalSelfState.model_validate(snapshot)
    return compact_developmental_self_context(state)


def _compact_social_self_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = SocialSelfState.model_validate(snapshot)
    return state.to_runtime_projection()


def _compact_embodied_self_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = EmbodiedSelfState.model_validate(snapshot)
    return state.to_runtime_projection()


def _compact_selfhood_integration_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = SelfhoodIntegrationState.model_validate(snapshot)
    return state.to_runtime_projection()


def _compact_initiative_self_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = InitiativeSelfState.model_validate(snapshot)
    return state.to_runtime_projection()


def _compact_initiative_realization_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = InitiativeRealizationState.model_validate(snapshot)
    return state.to_runtime_projection()


def _inject_developmental_self_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    developmental_self_store: Optional[DevelopmentalSelfStore] = None,
) -> Dict[str, Any]:
    store = developmental_self_store or DevelopmentalSelfStore()
    snapshot = store.load_snapshot(_resolve_developmental_self_identity_handle(state))
    if snapshot:
        runtime_summary["developmental_self_context"] = _compact_developmental_self_context(snapshot)
    return runtime_summary


def _inject_social_self_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    social_self_store: Optional[SocialSelfStore] = None,
) -> Dict[str, Any]:
    store = social_self_store or SocialSelfStore()
    snapshot = store.load_snapshot(_resolve_social_self_identity_handle(state))
    if snapshot:
        runtime_summary["social_self_context"] = _compact_social_self_context(snapshot)
    return runtime_summary


def _inject_embodied_self_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    embodied_self_store: Optional[EmbodiedSelfStore] = None,
) -> Dict[str, Any]:
    store = embodied_self_store or EmbodiedSelfStore()
    snapshot = store.load_snapshot(_resolve_embodied_self_identity_handle(state))
    if snapshot:
        runtime_summary["embodied_self_context"] = _compact_embodied_self_context(snapshot)
    return runtime_summary


def _inject_selfhood_integration_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    selfhood_integration_store: Optional[SelfhoodIntegrationStore] = None,
) -> Dict[str, Any]:
    store = selfhood_integration_store or SelfhoodIntegrationStore()
    snapshot = store.load_snapshot(_resolve_selfhood_integration_identity_handle(state))
    if snapshot:
        runtime_summary["selfhood_integration_context"] = _compact_selfhood_integration_context(snapshot)
    return runtime_summary


def _inject_initiative_self_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    initiative_self_store: Optional[InitiativeSelfStore] = None,
) -> Dict[str, Any]:
    store = initiative_self_store or InitiativeSelfStore()
    snapshot = store.load_snapshot(_resolve_initiative_self_identity_handle(state))
    if snapshot:
        runtime_summary["initiative_self_context"] = _compact_initiative_self_context(snapshot)
    return runtime_summary


def _inject_initiative_realization_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
    initiative_realization_store: Optional[InitiativeRealizationStore] = None,
) -> Dict[str, Any]:
    store = initiative_realization_store or InitiativeRealizationStore()
    snapshot = store.load_snapshot(_resolve_initiative_realization_identity_handle(state))
    if snapshot:
        runtime_summary["initiative_realization_context"] = _compact_initiative_realization_context(
            snapshot
        )
    return runtime_summary


def _inject_developmental_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    runtime_summary["developmental_context"] = _build_developmental_context(state)
    return runtime_summary


def _inject_social_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    runtime_summary["social_context"] = _build_social_context(state)
    return runtime_summary


def _inject_environment_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    runtime_summary["environment_context"] = _build_environment_context(state)
    return runtime_summary


def _inject_initiative_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    runtime_summary["initiative_context"] = _build_initiative_context(state)
    return runtime_summary


def _inject_host_proactive_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    runtime_summary["host_proactive_context"] = _build_host_proactive_context(state)
    return runtime_summary


def _resolve_reflection_target_type(target_id: str) -> ReflectionTargetType:
    prefix = str(target_id or "").split(":", 1)[0].strip().lower()
    mapping = {
        "decision": ReflectionTargetType.DECISION,
        "trajectory": ReflectionTargetType.TRAJECTORY,
        "maintenance": ReflectionTargetType.MAINTENANCE,
        "self_model": ReflectionTargetType.SELF_MODEL,
        "drive_state": ReflectionTargetType.DRIVE_STATE,
        "behavior": ReflectionTargetType.BEHAVIOR,
        "state": ReflectionTargetType.STATE,
    }
    return mapping.get(prefix, ReflectionTargetType.STATE)


def _build_seed_event(
    *,
    event_type: str,
    source: str,
    payload: Dict[str, Any],
    runtime_summary: Dict[str, Any],
    safety_context: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": SEED_SCHEMA_VERSION,
        "event_type": event_type,
        "source": source,
        "payload": payload,
        "runtime_summary": runtime_summary,
        "safety_context": safety_context,
        "timestamp": datetime.now().isoformat(),
    }


def _build_seed_status_from_result(*, result: Any, state: RuntimeV2State) -> str:
    if state.last_tool_result and not state.last_tool_result.get("success"):
        return "failure"
    if result.status == "blocked":
        return "blocked"
    if result.status in {"waiting_input", "resumable_pause"}:
        return "no_op"
    return "success"


def _build_host_action_summary(*, result: Any, state: RuntimeV2State) -> Dict[str, Any]:
    action_raw = state.last_model_action or {}
    action_type = action_raw.get("type")
    if not action_type:
        if state.last_tool_result:
            action_type = state.last_tool_result.get("tool") or "tool"
        elif result.reply_text:
            action_type = "host_reply"
        else:
            action_type = "host_wait"
    resolved_target = _resolved_target(state)
    return {
        "action_type": action_type,
        "target": resolved_target.get("path") or resolved_target.get("filename"),
        "status": _build_seed_status_from_result(result=result, state=state),
        "details": {
            "host_terminal_status": result.status,
            "delivery_kind": result.delivery_kind,
            "reply_length": len(result.reply_text or ""),
            "waiting_for_user_input": bool(state.waiting_for_user_input),
            "last_tool_result": state.last_tool_result,
        },
    }


def build_proto_self_ingress_event(
    *,
    session_id: str,
    turn_id: str,
    source: str,
    user_input: str,
    state: RuntimeV2State,
    self_model_store: Optional[SelfModelStore] = None,
    endogenous_drive_store: Optional[EndogenousDriveStore] = None,
    reflective_self_store: Optional[ReflectiveSelfStore] = None,
    developmental_self_store: Optional[DevelopmentalSelfStore] = None,
    social_self_store: Optional[SocialSelfStore] = None,
    embodied_self_store: Optional[EmbodiedSelfStore] = None,
    selfhood_integration_store: Optional[SelfhoodIntegrationStore] = None,
    initiative_self_store: Optional[InitiativeSelfStore] = None,
    initiative_realization_store: Optional[InitiativeRealizationStore] = None,
) -> Dict[str, Any]:
    risk_level = assess_risk_level(user_input)
    safety_context = _inject_private_proto_self_safety_overrides(
        {"risk_level": risk_level},
        state=state,
    )
    restore_observation = (state.ingress_context or {}).get("restore_observation")
    schema_version = resolve_proto_self_schema_version(state)
    if schema_version == "proto_self.v2":
        ingress_context = state.ingress_context or {}
        subject_profile = resolve_proto_self_subject_profile(state)
        runtime_summary = _inject_self_model_context(
            {
                "runtime": "runtime_v2",
                **_proto_self_state_scope_context(state),
                "restore_observation": restore_observation,
            },
            state=state,
            self_model_store=self_model_store,
        )
        runtime_summary = _inject_endogenous_drive_context(
            runtime_summary,
            state=state,
            endogenous_drive_store=endogenous_drive_store,
        )
        runtime_summary = _inject_reflective_self_context(
            runtime_summary,
            state=state,
            reflective_self_store=reflective_self_store,
        )
        runtime_summary = _inject_developmental_self_context(
            runtime_summary,
            state=state,
            developmental_self_store=developmental_self_store,
        )
        runtime_summary = _inject_social_self_context(
            runtime_summary,
            state=state,
            social_self_store=social_self_store,
        )
        runtime_summary = _inject_embodied_self_context(
            runtime_summary,
            state=state,
            embodied_self_store=embodied_self_store,
        )
        runtime_summary = _inject_selfhood_integration_context(
            runtime_summary,
            state=state,
            selfhood_integration_store=selfhood_integration_store,
        )
        runtime_summary = _inject_initiative_self_context(
            runtime_summary,
            state=state,
            initiative_self_store=initiative_self_store,
        )
        runtime_summary = _inject_initiative_realization_context(
            runtime_summary,
            state=state,
            initiative_realization_store=initiative_realization_store,
        )
        runtime_summary.update(
            {
                k: v
                for k, v in _seed_runtime_summary(state).items()
                if v is not None
            }
        )
        runtime_summary = _inject_social_context(runtime_summary, state=state)
        runtime_summary = _inject_developmental_context(runtime_summary, state=state)
        runtime_summary = _inject_environment_context(runtime_summary, state=state)
        runtime_summary = _inject_initiative_context(runtime_summary, state=state)
        runtime_summary = _inject_host_proactive_context(runtime_summary, state=state)
        runtime_summary = _inject_h1_canonical_shadow_context(runtime_summary, state=state)
        payload = {
            "schema_version": schema_version,
            "event_id": f"{session_id}_{turn_id}",
            "timestamp": datetime.now().isoformat(),
            "event": {
                "actor": "user",
                "source": source,
                "event_type": "user_message",
                "user_intent": user_input[:100] if user_input else None,
                "raw_text": user_input,
            },
            "subject_profile": subject_profile,
            "conversation_summary": {
                "session_id": session_id,
                "thread_id": session_id,
                "turn_id": turn_id,
            },
            "task_summary": {
                "pending_tasks": 1 if state.current_goal else 0,
                "blocked_tasks": 0,
            },
            "runtime_summary": runtime_summary,
            "safety_context": safety_context,
            "executed_action_prev": ingress_context.get("executed_action_prev"),
            "external_outcome": None,
            "intervention_context": ingress_context.get("intervention_context", {}),
            "prediction_snapshot_prev": ingress_context.get("prediction_snapshot_prev", {}),
        }
        if subject_profile == SEED_SUBJECT_PROFILE:
            payload["seed_event"] = _build_seed_event(
                event_type="user_event",
                source=source,
                payload={
                    "raw_text": user_input,
                    "user_intent": user_input[:100] if user_input else None,
                    "interaction_kind": ingress_context.get("interaction_kind"),
                    "conversation_act": ingress_context.get("conversation_act"),
                    "resolved_target_path": _resolved_target(state).get("path"),
                    "resolved_target_name": _resolved_target(state).get("filename"),
                },
                runtime_summary=_seed_runtime_summary(state),
                safety_context={**safety_context, "blocked": False},
            )
        return payload
    runtime_summary = _inject_h1_canonical_shadow_context(
        {
            "runtime": "runtime_v2",
            **_proto_self_state_scope_context(state),
            "restore_observation": restore_observation,
        },
        state=state,
    )
    return {
        "event_id": f"{session_id}_{turn_id}",
        "timestamp": datetime.now().isoformat(),
        "actor": "user",
        "source": source,
        "event_type": "user_message",
        "user_intent": user_input[:100] if user_input else None,
        "raw_text": user_input,
        "conversation_context": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": turn_id,
        },
        "task_context": {
            "pending_tasks": 1 if state.current_goal else 0,
            "blocked_tasks": 0,
        },
        "runtime_summary": runtime_summary,
        "safety_context": safety_context,
        "external_result": None,
    }


def build_external_result_event(
    *,
    session_id: str,
    turn_id: str,
    step: int,
    tool_result: Dict[str, Any],
    state: RuntimeV2State,
    self_model_store: Optional[SelfModelStore] = None,
    endogenous_drive_store: Optional[EndogenousDriveStore] = None,
    reflective_self_store: Optional[ReflectiveSelfStore] = None,
    developmental_self_store: Optional[DevelopmentalSelfStore] = None,
    social_self_store: Optional[SocialSelfStore] = None,
    embodied_self_store: Optional[EmbodiedSelfStore] = None,
    selfhood_integration_store: Optional[SelfhoodIntegrationStore] = None,
    initiative_self_store: Optional[InitiativeSelfStore] = None,
    initiative_realization_store: Optional[InitiativeRealizationStore] = None,
) -> Dict[str, Any]:
    failed = not tool_result.get("success")
    schema_version = resolve_proto_self_schema_version(state)
    if schema_version == "proto_self.v2":
        ingress_context = state.ingress_context or {}
        payload = {
            "schema_version": schema_version,
            "event_id": f"{session_id}_{turn_id}_tool_{step}",
            "timestamp": datetime.now().isoformat(),
            "event": {
                "actor": "system",
                "source": "runtime",
                "event_type": "tool_result",
                "user_intent": None,
                "raw_text": None,
            },
            "conversation_summary": {
                "session_id": session_id,
                "thread_id": session_id,
                "turn_id": turn_id,
            },
            "task_summary": {
                "pending_tasks": 1 if state.current_goal else 0,
                "blocked_tasks": 1 if failed else 0,
            },
            "runtime_summary": _inject_self_model_context(
                {
                    "runtime": "runtime_v2",
                    **_proto_self_state_scope_context(state),
                    **_seed_runtime_summary(state),
                },
                state=state,
                self_model_store=self_model_store,
            ),
            "safety_context": {
                "risk_level": risk_level_from_external_result(failed=failed),
            },
            "executed_action_prev": ingress_context.get("executed_action_prev"),
            "external_outcome": {
                "success": tool_result.get("success", False),
                "tool": tool_result.get("tool"),
                "exit_code": tool_result.get("exit_code"),
                "error": tool_result.get("stderr", "")[:200] if failed else None,
            },
            "intervention_context": ingress_context.get("intervention_context", {}),
            "prediction_snapshot_prev": ingress_context.get("prediction_snapshot_prev", {}),
        }
        subject_profile = resolve_proto_self_subject_profile(state)
        payload["runtime_summary"] = _inject_endogenous_drive_context(
            payload["runtime_summary"],
            state=state,
            endogenous_drive_store=endogenous_drive_store,
        )
        payload["runtime_summary"] = _inject_reflective_self_context(
            payload["runtime_summary"],
            state=state,
            reflective_self_store=reflective_self_store,
        )
        payload["runtime_summary"] = _inject_developmental_self_context(
            payload["runtime_summary"],
            state=state,
            developmental_self_store=developmental_self_store,
        )
        payload["runtime_summary"] = _inject_social_self_context(
            payload["runtime_summary"],
            state=state,
            social_self_store=social_self_store,
        )
        payload["runtime_summary"] = _inject_embodied_self_context(
            payload["runtime_summary"],
            state=state,
            embodied_self_store=embodied_self_store,
        )
        payload["runtime_summary"] = _inject_selfhood_integration_context(
            payload["runtime_summary"],
            state=state,
            selfhood_integration_store=selfhood_integration_store,
        )
        payload["runtime_summary"] = _inject_initiative_self_context(
            payload["runtime_summary"],
            state=state,
            initiative_self_store=initiative_self_store,
        )
        payload["runtime_summary"] = _inject_initiative_realization_context(
            payload["runtime_summary"],
            state=state,
            initiative_realization_store=initiative_realization_store,
        )
        payload["runtime_summary"] = _inject_social_context(
            payload["runtime_summary"],
            state=state,
        )
        payload["runtime_summary"] = _inject_developmental_context(
            payload["runtime_summary"],
            state=state,
        )
        payload["runtime_summary"] = _inject_environment_context(
            payload["runtime_summary"],
            state=state,
        )
        payload["runtime_summary"] = _inject_initiative_context(
            payload["runtime_summary"],
            state=state,
        )
        payload["runtime_summary"] = _inject_host_proactive_context(
            payload["runtime_summary"],
            state=state,
        )
        payload["runtime_summary"] = _inject_h1_canonical_shadow_context(
            payload["runtime_summary"],
            state=state,
        )
        payload["subject_profile"] = subject_profile
        if subject_profile == SEED_SUBJECT_PROFILE:
            payload["seed_event"] = _build_seed_event(
                event_type="exec_result",
                source="runtime",
                payload={
                    "action_type": tool_result.get("tool") or "tool",
                    "status": "failure" if failed else "success",
                    "target": _resolved_target(state).get("path") or _resolved_target(state).get("filename"),
                    "observed_gain": 0.0 if failed else 0.4,
                    "error": tool_result.get("stderr", "")[:200] if failed else None,
                    "details": {
                        "tool": tool_result.get("tool"),
                        "exit_code": tool_result.get("exit_code"),
                    },
                },
                runtime_summary=_seed_runtime_summary(state),
                safety_context={
                    "risk_level": risk_level_from_external_result(failed=failed),
                    "blocked": failed,
                },
            )
        return payload
    runtime_summary = _inject_h1_canonical_shadow_context(
        {
            "runtime": "runtime_v2",
            **_proto_self_state_scope_context(state),
        },
        state=state,
    )
    return {
        "event_id": f"{session_id}_{turn_id}_tool_{step}",
        "timestamp": datetime.now().isoformat(),
        "actor": "system",
        "source": "runtime",
        "event_type": "tool_result",
        "user_intent": None,
        "raw_text": None,
        "conversation_context": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": turn_id,
        },
        "task_context": {
            "pending_tasks": 1 if state.current_goal else 0,
            "blocked_tasks": 1 if failed else 0,
        },
        "runtime_summary": runtime_summary,
        "safety_context": {
            "risk_level": risk_level_from_external_result(failed=failed),
        },
        "external_result": {
            "success": tool_result.get("success", False),
            "tool": tool_result.get("tool"),
            "exit_code": tool_result.get("exit_code"),
            "error": tool_result.get("stderr", "")[:200] if failed else None,
        },
    }


def build_finalized_result_event(
    *,
    session_id: str,
    turn_id: str,
    result: Any,
    state: RuntimeV2State,
    self_model_store: Optional[SelfModelStore] = None,
    endogenous_drive_store: Optional[EndogenousDriveStore] = None,
    reflective_self_store: Optional[ReflectiveSelfStore] = None,
    developmental_self_store: Optional[DevelopmentalSelfStore] = None,
    social_self_store: Optional[SocialSelfStore] = None,
    embodied_self_store: Optional[EmbodiedSelfStore] = None,
    selfhood_integration_store: Optional[SelfhoodIntegrationStore] = None,
    initiative_self_store: Optional[InitiativeSelfStore] = None,
    initiative_realization_store: Optional[InitiativeRealizationStore] = None,
) -> Optional[Dict[str, Any]]:
    if resolve_proto_self_schema_version(state) != "proto_self.v2":
        return None
    subject_profile = resolve_proto_self_subject_profile(state)
    ingress_context = state.ingress_context or {}
    host_action = _build_host_action_summary(result=result, state=state)
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": f"{session_id}_{turn_id}_finalized",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "system",
            "source": "runtime",
            "event_type": "turn_finalized",
            "user_intent": None,
            "raw_text": None,
        },
        "subject_profile": subject_profile,
        "conversation_summary": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": turn_id,
        },
        "task_summary": {
            "pending_tasks": 1 if state.current_goal else 0,
            "blocked_tasks": 1 if result.status == "blocked" else 0,
        },
        "runtime_summary": _inject_self_model_context(
            {
                "runtime": "runtime_v2",
                **_proto_self_state_scope_context(state),
                **_seed_runtime_summary(state),
            },
            state=state,
            self_model_store=self_model_store,
        ),
        "safety_context": {
            "risk_level": ingress_context.get("risk_level") or "low",
        },
        "executed_action_prev": {
            "kind": host_action["action_type"],
            "status": host_action["status"],
        },
        "external_outcome": None,
        "intervention_context": ingress_context.get("intervention_context", {}),
        "prediction_snapshot_prev": ingress_context.get("prediction_snapshot_prev", {}),
    }
    payload["runtime_summary"] = _inject_endogenous_drive_context(
        payload["runtime_summary"],
        state=state,
        endogenous_drive_store=endogenous_drive_store,
    )
    payload["runtime_summary"] = _inject_reflective_self_context(
        payload["runtime_summary"],
        state=state,
        reflective_self_store=reflective_self_store,
    )
    payload["runtime_summary"] = _inject_developmental_self_context(
        payload["runtime_summary"],
        state=state,
        developmental_self_store=developmental_self_store,
    )
    payload["runtime_summary"] = _inject_social_self_context(
        payload["runtime_summary"],
        state=state,
        social_self_store=social_self_store,
    )
    payload["runtime_summary"] = _inject_embodied_self_context(
        payload["runtime_summary"],
        state=state,
        embodied_self_store=embodied_self_store,
    )
    payload["runtime_summary"] = _inject_selfhood_integration_context(
        payload["runtime_summary"],
        state=state,
        selfhood_integration_store=selfhood_integration_store,
    )
    payload["runtime_summary"] = _inject_initiative_self_context(
        payload["runtime_summary"],
        state=state,
        initiative_self_store=initiative_self_store,
    )
    payload["runtime_summary"] = _inject_initiative_realization_context(
        payload["runtime_summary"],
        state=state,
        initiative_realization_store=initiative_realization_store,
    )
    payload["runtime_summary"] = _inject_social_context(
        payload["runtime_summary"],
        state=state,
    )
    payload["runtime_summary"] = _inject_developmental_context(
        payload["runtime_summary"],
        state=state,
    )
    payload["runtime_summary"] = _inject_environment_context(
        payload["runtime_summary"],
        state=state,
    )
    payload["runtime_summary"] = _inject_initiative_context(
        payload["runtime_summary"],
        state=state,
    )
    payload["runtime_summary"] = _inject_host_proactive_context(
        payload["runtime_summary"],
        state=state,
    )
    payload["runtime_summary"] = _inject_h1_canonical_shadow_context(
        payload["runtime_summary"],
        state=state,
    )
    if subject_profile == SEED_SUBJECT_PROFILE:
        payload["seed_event"] = _build_seed_event(
            event_type="exec_result",
            source="runtime",
            payload=host_action,
            runtime_summary=_seed_runtime_summary(state),
            safety_context={
                "risk_level": ingress_context.get("risk_level") or "low",
                "blocked": result.status == "blocked",
            },
        )
    return payload


def build_idle_check_event(
    *,
    session_id: str,
    turn_id: str,
    state: RuntimeV2State,
    self_model_store: Optional[SelfModelStore] = None,
    endogenous_drive_store: Optional[EndogenousDriveStore] = None,
    reflective_self_store: Optional[ReflectiveSelfStore] = None,
    developmental_self_store: Optional[DevelopmentalSelfStore] = None,
    social_self_store: Optional[SocialSelfStore] = None,
    embodied_self_store: Optional[EmbodiedSelfStore] = None,
    selfhood_integration_store: Optional[SelfhoodIntegrationStore] = None,
    initiative_self_store: Optional[InitiativeSelfStore] = None,
    initiative_realization_store: Optional[InitiativeRealizationStore] = None,
) -> Optional[Dict[str, Any]]:
    if resolve_proto_self_schema_version(state) != "proto_self.v2":
        return None
    subject_profile = resolve_proto_self_subject_profile(state)
    if subject_profile != SEED_SUBJECT_PROFILE:
        return None
    event = {
        "schema_version": "proto_self.v2",
        "event_id": f"{session_id}_{turn_id}_idle",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "system",
            "source": "runtime",
            "event_type": "idle_check",
            "user_intent": None,
            "raw_text": None,
        },
        "subject_profile": subject_profile,
        "seed_event": _build_seed_event(
            event_type="idle_check",
            source="runtime",
            payload={
                "raw_text": None,
                "resolved_target_path": _resolved_target(state).get("path"),
                "resolved_target_name": _resolved_target(state).get("filename"),
            },
            runtime_summary=_seed_runtime_summary(state),
            safety_context={"risk_level": "low", "blocked": False},
        ),
        "conversation_summary": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": turn_id,
        },
        "task_summary": {
            "pending_tasks": 1 if state.current_goal else 0,
            "blocked_tasks": 0,
        },
        "runtime_summary": _inject_self_model_context(
            {
                "runtime": "runtime_v2",
                **_proto_self_state_scope_context(state),
                **_seed_runtime_summary(state),
            },
            state=state,
            self_model_store=self_model_store,
        ),
        "safety_context": {
            "risk_level": "low",
        },
        "executed_action_prev": None,
        "external_outcome": None,
        "intervention_context": {},
        "prediction_snapshot_prev": {},
    }
    event["runtime_summary"] = _inject_endogenous_drive_context(
        event["runtime_summary"],
        state=state,
        endogenous_drive_store=endogenous_drive_store,
    )
    event["runtime_summary"] = _inject_reflective_self_context(
        event["runtime_summary"],
        state=state,
        reflective_self_store=reflective_self_store,
    )
    event["runtime_summary"] = _inject_developmental_self_context(
        event["runtime_summary"],
        state=state,
        developmental_self_store=developmental_self_store,
    )
    event["runtime_summary"] = _inject_social_self_context(
        event["runtime_summary"],
        state=state,
        social_self_store=social_self_store,
    )
    event["runtime_summary"] = _inject_embodied_self_context(
        event["runtime_summary"],
        state=state,
        embodied_self_store=embodied_self_store,
    )
    event["runtime_summary"] = _inject_selfhood_integration_context(
        event["runtime_summary"],
        state=state,
        selfhood_integration_store=selfhood_integration_store,
    )
    event["runtime_summary"] = _inject_initiative_self_context(
        event["runtime_summary"],
        state=state,
        initiative_self_store=initiative_self_store,
    )
    event["runtime_summary"] = _inject_initiative_realization_context(
        event["runtime_summary"],
        state=state,
        initiative_realization_store=initiative_realization_store,
    )
    event["runtime_summary"] = _inject_social_context(
        event["runtime_summary"],
        state=state,
    )
    event["runtime_summary"] = _inject_developmental_context(
        event["runtime_summary"],
        state=state,
    )
    event["runtime_summary"] = _inject_environment_context(
        event["runtime_summary"],
        state=state,
    )
    event["runtime_summary"] = _inject_initiative_context(
        event["runtime_summary"],
        state=state,
    )
    event["runtime_summary"] = _inject_host_proactive_context(
        event["runtime_summary"],
        state=state,
    )
    event["runtime_summary"] = _inject_h1_canonical_shadow_context(
        event["runtime_summary"],
        state=state,
    )
    return event


def build_developmental_tick_event(
    *,
    session_id: str,
    turn_id: str,
    state: RuntimeV2State,
    observation_source: str = "synthetic",
    trigger: str = "idle",
    idle_seconds: float = 0.0,
    unresolved_tensions: Optional[list] = None,
    long_term_goals: Optional[list] = None,
    observation_refs: Optional[list] = None,
    state_snapshot: Optional[Dict[str, Any]] = None,
    replay_seed: Optional[int] = None,
    force_enable: bool = False,
    self_model_store: Optional[SelfModelStore] = None,
    endogenous_drive_store: Optional[EndogenousDriveStore] = None,
    reflective_self_store: Optional[ReflectiveSelfStore] = None,
    developmental_self_store: Optional[DevelopmentalSelfStore] = None,
    social_self_store: Optional[SocialSelfStore] = None,
    embodied_self_store: Optional[EmbodiedSelfStore] = None,
    selfhood_integration_store: Optional[SelfhoodIntegrationStore] = None,
    initiative_self_store: Optional[InitiativeSelfStore] = None,
    initiative_realization_store: Optional[InitiativeRealizationStore] = None,
) -> Optional[Dict[str, Any]]:
    if resolve_proto_self_schema_version(state) != "proto_self.v2":
        return None
    if not force_enable and not ENABLE_MVP12_SANDBOX:
        return None
    subject_profile = resolve_proto_self_subject_profile(state)
    event_type = "developmental_replay" if observation_source == "replay" else "developmental_tick"
    runtime_summary = _inject_self_model_context(
        {
            "runtime": "runtime_v2",
            **_proto_self_state_scope_context(state),
            **_seed_runtime_summary(state),
            "developmental_mode": "shadow_observe",
            "observation_source": observation_source,
            "developmental_trigger": trigger,
            "idle_seconds": idle_seconds,
            "max_candidates": 5,
        },
        state=state,
        self_model_store=self_model_store,
    )
    runtime_summary = _inject_endogenous_drive_context(
        runtime_summary,
        state=state,
        endogenous_drive_store=endogenous_drive_store,
    )
    runtime_summary = _inject_reflective_self_context(
        runtime_summary,
        state=state,
        reflective_self_store=reflective_self_store,
    )
    runtime_summary = _inject_developmental_self_context(
        runtime_summary,
        state=state,
        developmental_self_store=developmental_self_store,
    )
    runtime_summary = _inject_social_self_context(
        runtime_summary,
        state=state,
        social_self_store=social_self_store,
    )
    runtime_summary = _inject_embodied_self_context(
        runtime_summary,
        state=state,
        embodied_self_store=embodied_self_store,
    )
    runtime_summary = _inject_selfhood_integration_context(
        runtime_summary,
        state=state,
        selfhood_integration_store=selfhood_integration_store,
    )
    runtime_summary = _inject_initiative_self_context(
        runtime_summary,
        state=state,
        initiative_self_store=initiative_self_store,
    )
    runtime_summary = _inject_initiative_realization_context(
        runtime_summary,
        state=state,
        initiative_realization_store=initiative_realization_store,
    )
    runtime_summary = _inject_social_context(runtime_summary, state=state)
    runtime_summary = _inject_developmental_context(
        runtime_summary,
        state=state,
    )
    runtime_summary = _inject_environment_context(runtime_summary, state=state)
    runtime_summary = _inject_initiative_context(runtime_summary, state=state)
    runtime_summary = _inject_host_proactive_context(runtime_summary, state=state)
    runtime_summary = _inject_h1_canonical_shadow_context(runtime_summary, state=state)
    if replay_seed is not None:
        runtime_summary["replay_seed"] = replay_seed
    return {
        "schema_version": "proto_self.v2",
        "event_id": f"{session_id}_{turn_id}_developmental",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "system",
            "source": "runtime",
            "event_type": event_type,
            "user_intent": None,
            "raw_text": None,
        },
        "subject_profile": subject_profile,
        "conversation_summary": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": turn_id,
        },
        "task_summary": {
            "pending_tasks": 1 if state.current_goal else 0,
            "blocked_tasks": 0,
        },
        "runtime_summary": runtime_summary,
        "safety_context": {
            "risk_level": "low",
        },
        "executed_action_prev": None,
        "external_outcome": None,
        "intervention_context": {
            "developmental_input": {
                "state_snapshot": dict(state_snapshot or {}),
                "unresolved_tensions": list(unresolved_tensions or []),
                "long_term_goals": list(long_term_goals or []),
                "observation_refs": list(observation_refs or []),
            }
        },
        "prediction_snapshot_prev": {},
    }


def build_response_plan_payload(*, result: Any) -> Dict[str, Any]:
    reply = getattr(result, "reply", None)
    reply_metadata = dict(getattr(reply, "metadata", None) or {})
    final_text = str(getattr(result, "reply_text", "") or "").strip()
    final_text_preview = str(reply_metadata.get("final_text_preview") or "").strip() or None
    final_text_hash = str(reply_metadata.get("final_text_hash") or "").strip() or None
    final_text_length = reply_metadata.get("final_text_length")
    payload = {
        "status": result.status,
        "delivery_kind": result.delivery_kind if reply else None,
        "reply_length": len(final_text) if final_text else 0,
        "reply_authority": reply_metadata.get("reply_authority"),
        "reply_origin": reply_metadata.get("reply_origin"),
        "chat_cadence_mode": reply_metadata.get("chat_cadence_mode"),
        "output_check_reason": reply_metadata.get("output_check_reason"),
        "intent_gate_reason": reply_metadata.get("intent_gate_reason"),
    }
    metadata: Dict[str, Any] = {}
    if reply_metadata.get("chat_expression_hint"):
        metadata["chat_expression_hint"] = dict(reply_metadata.get("chat_expression_hint") or {})
    if reply_metadata.get("response_tendency_summary"):
        metadata["response_tendency_summary"] = dict(reply_metadata.get("response_tendency_summary") or {})
    if reply_metadata.get("recent_result_context"):
        metadata["recent_result_context"] = dict(reply_metadata.get("recent_result_context") or {})
    if reply_metadata.get("result_binding_source_turn"):
        metadata["result_binding_source_turn"] = reply_metadata.get("result_binding_source_turn")
    if reply_metadata.get("recent_result_binding") is not None:
        metadata["recent_result_binding"] = bool(reply_metadata.get("recent_result_binding"))
    if reply_metadata.get("correction_context") is not None:
        metadata["correction_context"] = bool(reply_metadata.get("correction_context"))
    if reply_metadata.get("pending_result_continuation"):
        metadata["pending_result_continuation"] = dict(reply_metadata.get("pending_result_continuation") or {})
    if final_text_preview:
        metadata["final_text_preview"] = final_text_preview
    elif final_text:
        metadata["final_text_preview"] = final_text[:200]
    if final_text_hash:
        metadata["final_text_hash"] = final_text_hash
    if final_text_length is not None:
        metadata["final_text_length"] = final_text_length
    elif final_text:
        metadata["final_text_length"] = len(final_text)
    if metadata:
        payload["metadata"] = metadata
    state = getattr(result, "state", None)
    ingress_context = getattr(state, "ingress_context", None) or {}
    restore_observation = ingress_context.get("restore_observation")
    if restore_observation:
        payload["restore_observation"] = dict(restore_observation)
    proto_self_context = getattr(state, "proto_self_context", None) or {}
    subject_profile = proto_self_context.get("subject_profile") or ingress_context.get("proto_self_subject_profile")
    if subject_profile:
        payload["proto_self_subject_profile"] = subject_profile
    candidate_actions = list(proto_self_context.get("candidate_actions") or [])
    if candidate_actions:
        payload["candidate_action_types"] = [item.get("action_type") for item in candidate_actions]
    governor_hint = proto_self_context.get("governor_hint") or {}
    if governor_hint:
        payload["proto_self_governor_hint"] = dict(governor_hint)
    return payload


@dataclass
class RuntimeV2ProtoSelfRuntime:
    adapter: Any
    trace_bridge: Any = None
    evidence_collector_factory: Optional[Any] = None
    self_model_store: Optional[SelfModelStore] = None
    endogenous_drive_store: Optional[EndogenousDriveStore] = None
    reflective_self_store: Optional[ReflectiveSelfStore] = None
    developmental_self_store: Optional[DevelopmentalSelfStore] = None
    social_self_store: Optional[SocialSelfStore] = None
    embodied_self_store: Optional[EmbodiedSelfStore] = None
    selfhood_integration_store: Optional[SelfhoodIntegrationStore] = None
    initiative_self_store: Optional[InitiativeSelfStore] = None

    def _resolve_collector(self, evidence_collector: Optional[Any]) -> Optional[Any]:
        if evidence_collector is not None:
            return evidence_collector
        if self.evidence_collector_factory is None:
            return None
        try:
            return self.evidence_collector_factory()
        except Exception as exc:
            logger.warning(f"[E4-EVIDENCE] Failed to resolve collector: {exc}")
            return None

    initiative_realization_store: Optional[InitiativeRealizationStore] = None
    def _capture_trace_in_ledger_or_bridge(
        self,
        *,
        proto_self_result: Dict[str, Any],
        collector: Optional[Any],
        bridge_stage: str,
    ) -> None:
        trace_payload = proto_self_result.get("trace_payload")
        if not trace_payload:
            return

        if collector is not None and hasattr(collector, "capture_openemotion_trace"):
            collector.capture_openemotion_trace(trace_payload, stage=bridge_stage)
            return

        if self.trace_bridge:
            self.trace_bridge.write(trace_payload)

    def _apply_self_model_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("self_model_delta") or {})
        if not delta:
            return None

        store = self.self_model_store or SelfModelStore()
        identity_handle = _resolve_self_model_identity_handle(state)
        current_model = store.load(identity_handle) or create_default_self_model(identity_handle)
        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        confidence_meta = dict(proto_self_result.get("confidence_meta") or {})
        update_packet_hash = trace_payload.get("update_packet_hash")
        supporting_evidence = [f"event:{proto_self_result.get('event_id', 'unknown')}"]
        if update_packet_hash:
            supporting_evidence.append(f"trace:{update_packet_hash}")
        for item in list(confidence_meta.get("self_model_supporting_evidence") or []):
            value = str(item or "").strip()
            if value and value not in supporting_evidence:
                supporting_evidence.append(value)
        request = SelfModelUpdateRequest(
            delta=delta,
            update_mode=str(confidence_meta.get("self_model_update_mode") or "append_observation"),
            update_source=str(confidence_meta.get("self_model_update_source") or "proto_self_v2"),
            trace_reference=str(
                confidence_meta.get("self_model_trace_reference")
                or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
            ),
            confidence_class=str(confidence_meta.get("self_model_confidence_class") or "medium"),
            supporting_evidence=supporting_evidence,
            candidate_id=confidence_meta.get("self_model_candidate_id"),
        )
        writeback = apply_governed_writeback(
            store=store,
            current_model=current_model,
            request=request,
            revisions=store.load_revision_log(identity_handle),
        ).to_dict()
        proto_self_result["self_model_writeback"] = writeback
        return writeback

    def _apply_endogenous_drive_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("endogenous_drive_delta") or {})
        if not delta:
            return None

        identity_handle = _resolve_endogenous_drive_identity_handle(state)
        store = self.endogenous_drive_store or EndogenousDriveStore(default_identity=identity_handle)
        current_state = store.load(identity_handle) or seed_default_state()
        owner = EndogenousDriveOwner(initial_state=current_state, store=store)
        confidence_meta = dict(proto_self_result.get("confidence_meta") or {})
        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        try:
            applied = owner.apply_owner_delta(delta)
            record = owner.persist(
                update_source=str(confidence_meta.get("endogenous_drive_update_source") or "proto_self_v2"),
                trace_reference=str(
                    confidence_meta.get("endogenous_drive_trace_reference")
                    or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
                ),
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": applied.get("changed_fields", []),
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_payload.get("update_packet_hash"),
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_payload.get("update_packet_hash"),
            }
        proto_self_result["endogenous_drive_writeback"] = writeback
        return writeback

    def _apply_reflective_self_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("reflective_self_delta") or {})
        candidates = list(proto_self_result.get("revision_proposal_candidates") or [])
        writeback_candidate = dict(proto_self_result.get("reflection_writeback_candidate") or {})
        if not delta and not candidates and not writeback_candidate:
            return None

        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        trace_reference = trace_payload.get("update_packet_hash")
        if writeback_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "reflection_writeback_requires_proposal_only",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["reflective_self_writeback"] = writeback
            return writeback
        if writeback_candidate.get("behavioral_authority") not in {None, "none"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "reflection_writeback_behavioral_authority_must_remain_none",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["reflective_self_writeback"] = writeback
            return writeback

        identity_handle = _resolve_reflective_self_identity_handle(state)
        store = self.reflective_self_store or ReflectiveSelfStore(default_identity=identity_handle)
        current_state = store.load(identity_handle) or ReflectiveSelfState()
        owner = ReflectiveSelfOwner(initial_state=current_state, store=store)
        confidence_meta = dict(proto_self_result.get("confidence_meta") or {})
        resolved_trace_reference = str(
            confidence_meta.get("reflective_self_trace_reference")
            or trace_reference
            or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
        )

        target_ids = list(writeback_candidate.get("target_ids") or delta.get("target_ids") or [])
        if not target_ids:
            target_ids = [
                str(item.get("target_id") or "").strip()
                for item in candidates
                if str(item.get("target_id") or "").strip()
            ]
        target_ids = [target_id for target_id in target_ids if target_id]

        changed_fields: list[str] = []
        for target_id in target_ids[:3]:
            owner.upsert_target(
                target_id=target_id,
                target_type=_resolve_reflection_target_type(target_id),
                reference=target_id,
                reason="proto_self_reflection_candidate",
                salience=0.7,
                evidence_refs=[resolved_trace_reference],
            )
        if target_ids:
            changed_fields.append("reflection_targets")

        proposal_count = 0
        for candidate in candidates:
            target_id = str(candidate.get("target_id") or "reflective_self").strip()
            proposal = owner.propose_revision(
                target_layer=target_id,
                proposed_change={
                    "candidate_id": candidate.get("candidate_id"),
                    "reason": candidate.get("reason"),
                    "source": "proto_self_v2",
                    "target_ids": target_ids[:3],
                },
                justification=str(candidate.get("reason") or "proto_self reflective proposal"),
                required_gate=str(candidate.get("required_gate") or "reflection_writeback_gate"),
                requested_effects=list(candidate.get("requested_effects") or []),
            )
            owner.set_proposal_gate_status(
                proposal.proposal_id,
                status="held",
                gate_verdict="allow_writeback",
                gate_reference=resolved_trace_reference,
                reason="proposal_only_candidate_recorded",
            )
            proposal_count += 1
        if proposal_count:
            changed_fields.append("revision_proposals")
        elif target_ids:
            owner.add_unresolved_item(
                summary=f"reflective follow-up pending for {target_ids[0]}",
                linked_record_id=None,
                severity=0.55,
            )
            changed_fields.append("unresolved_reflection_items")

        try:
            record = owner.persist(
                update_source=str(confidence_meta.get("reflective_self_update_source") or "proto_self_v2"),
                trace_reference=resolved_trace_reference,
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": sorted(set(changed_fields)),
                    "proposal_count": proposal_count,
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_reference or resolved_trace_reference,
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_reference or resolved_trace_reference,
            }
        proto_self_result["reflective_self_writeback"] = writeback
        return writeback

    def _apply_developmental_self_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("developmental_self_delta") or {})
        candidates = list(proto_self_result.get("developmental_proposal_candidates") or [])
        continuity_snapshot = dict(proto_self_result.get("developmental_continuity_snapshot") or {})
        priority_hints = dict(proto_self_result.get("developmental_priority_hints") or {})
        audit_entries = list(proto_self_result.get("developmental_audit_entries") or [])
        writeback_candidate = dict(proto_self_result.get("developmental_writeback_candidate") or {})
        if not delta and not candidates and not continuity_snapshot and not writeback_candidate:
            return None

        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        trace_reference = str(
            trace_payload.get("update_packet_hash")
            or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
        )

        if writeback_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "developmental_writeback_requires_proposal_only",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["developmental_writeback"] = writeback
            return writeback
        if writeback_candidate.get("behavioral_authority") not in {None, "none"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "developmental_writeback_behavioral_authority_must_remain_none",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["developmental_writeback"] = writeback
            return writeback
        if writeback_candidate.get("required_gate") not in {None, DEVELOPMENTAL_WRITEBACK_GATE}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "developmental_writeback_requires_formal_gate",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["developmental_writeback"] = writeback
            return writeback

        identity_handle = _resolve_developmental_self_identity_handle(state)
        store = self.developmental_self_store or DevelopmentalSelfStore(default_identity=identity_handle)
        current_state = store.load(identity_handle) or DevelopmentalSelfState(identity_handle=identity_handle)
        current_state.identity_handle = identity_handle
        current_state.developmental_identity_anchor.self_model_identity = identity_handle
        owner = DevelopmentalSelfOwner(initial_state=current_state, store=store)

        changed_fields: list[str] = []
        if continuity_snapshot:
            trajectory_summary = dict(continuity_snapshot.get("trajectory_summary") or {})
            if trajectory_summary:
                owner.set_trajectory_summary(
                    current_arc=str(trajectory_summary.get("current_arc") or "continuity_first"),
                    current_phase=str(trajectory_summary.get("current_phase") or "baseline"),
                    recent_shift=str(trajectory_summary.get("recent_shift") or ""),
                    continuity_note=str(trajectory_summary.get("continuity_note") or ""),
                    source_refs=list(trajectory_summary.get("source_refs") or [trace_reference]),
                )
                changed_fields.append("trajectory_summary")
            owner.set_continuity_metrics(
                continuity_score=float(continuity_snapshot.get("continuity_score") or owner.state.continuity_score),
                growth_pressure=float(continuity_snapshot.get("growth_pressure") or owner.state.growth_pressure),
                stagnation_signal=float(continuity_snapshot.get("stagnation_signal") or owner.state.stagnation_signal),
                identity_preservation_confidence=float(
                    continuity_snapshot.get("identity_preservation_confidence")
                    or owner.state.identity_preservation_confidence
                ),
                developmental_risk_index=float(
                    continuity_snapshot.get("developmental_risk_index")
                    or owner.state.developmental_risk_index
                ),
            )
            changed_fields.append("continuity_metrics")
            if continuity_snapshot.get("continuity_gap") is not None:
                owner.add_continuity_marker(
                    marker_type=ContinuityMarkerType.CONTINUITY_GAP,
                    reference=trace_reference,
                    continuity_weight=float(continuity_snapshot.get("continuity_gap") or 0.0),
                    note="proto_self developmental continuity snapshot",
                    source_refs=[trace_reference],
                )
                changed_fields.append("continuity_markers")

        created_proposals = []
        promotion_count = 0
        for candidate in candidates[:3]:
            if candidate.get("proposal_discipline") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {"gate_verdict": "reject", "reason": "developmental_candidate_requires_proposal_only"},
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["developmental_writeback"] = writeback
                return writeback
            if candidate.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "developmental_candidate_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["developmental_writeback"] = writeback
                return writeback
            if candidate.get("required_gate") not in {None, DEVELOPMENTAL_WRITEBACK_GATE}:
                writeback = {
                    "decision": {"gate_verdict": "reject", "reason": "developmental_candidate_requires_formal_gate"},
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["developmental_writeback"] = writeback
                return writeback
            try:
                promotion_level = PromotionLevel(
                    str(
                        candidate.get("promotion_level")
                        or writeback_candidate.get("promotion_level")
                        or priority_hints.get("promotion_budget")
                        or "shadow_only"
                    )
                )
            except ValueError:
                writeback = {
                    "decision": {"gate_verdict": "reject", "reason": "invalid_developmental_promotion_level"},
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["developmental_writeback"] = writeback
                return writeback

            proposal = owner.add_proposal(
                proposal_kind=str(candidate.get("reason") or "developmental_continuity"),
                summary=f"developmental proposal for {candidate.get('reason') or 'continuity'}",
                proposed_adjustment={
                    "developmental_self_delta": delta,
                    "continuity_snapshot": continuity_snapshot,
                    "priority_hints": priority_hints,
                    "surface_reasons": list(candidate.get("surface_reasons") or []),
                },
                justification=f"proto_self developmental proposal from {trace_reference}",
                source_refs=[trace_reference],
                requested_effects=list(candidate.get("requested_effects") or []),
                promotion_level=promotion_level,
            )
            created_proposals.append(proposal.proposal_id)
        if created_proposals:
            changed_fields.append("proposal_history")

        if writeback_candidate and created_proposals:
            try:
                queue_level = PromotionLevel(str(writeback_candidate.get("promotion_level") or "shadow_only"))
            except ValueError:
                queue_level = PromotionLevel.SHADOW_ONLY
            for proposal_id in created_proposals:
                owner.queue_promotion(
                    source_proposal_id=proposal_id,
                    summary=f"review developmental proposal {proposal_id}",
                    promotion_level=queue_level,
                )
                promotion_count += 1
            if promotion_count:
                changed_fields.append("promotion_queue")

        for audit_entry in audit_entries[:8]:
            owner.record_governance_event(
                event_type=str(audit_entry.get("kind") or "developmental_signal"),
                reference_id=str(audit_entry.get("reason") or trace_reference),
                gate_verdict="allow_writeback",
                details={
                    "trace_reference": trace_reference,
                    "source": "proto_self_v2",
                },
            )
        owner.record_governance_event(
            event_type="developmental_writeback",
            reference_id=created_proposals[0] if created_proposals else trace_reference,
            gate_verdict="allow_writeback",
            details={
                "trace_reference": trace_reference,
                "proposal_candidate_count": len(candidates),
                "promotion_count": promotion_count,
                "proposal_only": True,
                "behavioral_authority": "none",
            },
        )
        changed_fields.append("governance_ledger")

        try:
            record = owner.persist(
                update_source=str(writeback_candidate.get("source") or "proto_self_v2"),
                trace_reference=trace_reference,
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": sorted(set(changed_fields)),
                    "proposal_count": len(created_proposals),
                    "promotion_count": promotion_count,
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_reference,
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_reference,
            }
        proto_self_result["developmental_writeback"] = writeback
        return writeback

    def _apply_social_self_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("social_self_delta") or {})
        relation_candidates = list(proto_self_result.get("relation_update_candidates") or [])
        trust_commitment_snapshot = dict(proto_self_result.get("trust_commitment_snapshot") or {})
        social_policy_hints = dict(proto_self_result.get("social_policy_hints") or {})
        repair_candidates = list(proto_self_result.get("repair_proposal_candidates") or [])
        writeback_candidate = dict(proto_self_result.get("social_writeback_candidate") or {})
        if not delta and not relation_candidates and not trust_commitment_snapshot and not writeback_candidate:
            return None

        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        trace_reference = str(
            trace_payload.get("update_packet_hash")
            or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
        )

        if writeback_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": "social_writeback_requires_proposal_only"},
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["social_writeback"] = writeback
            return writeback
        if writeback_candidate.get("behavioral_authority") not in {None, "none"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "social_writeback_behavioral_authority_must_remain_none",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["social_writeback"] = writeback
            return writeback
        if writeback_candidate.get("required_gate") not in {None, SOCIAL_WRITEBACK_GATE}:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": "social_writeback_requires_formal_gate"},
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["social_writeback"] = writeback
            return writeback

        for candidate in [*relation_candidates[:3], *repair_candidates[:3]]:
            if candidate.get("proposal_discipline") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {"gate_verdict": "reject", "reason": "social_candidate_requires_proposal_only"},
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["social_writeback"] = writeback
                return writeback
            if candidate.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "social_candidate_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["social_writeback"] = writeback
                return writeback
            if candidate.get("required_gate") not in {None, SOCIAL_WRITEBACK_GATE}:
                writeback = {
                    "decision": {"gate_verdict": "reject", "reason": "social_candidate_requires_formal_gate"},
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["social_writeback"] = writeback
                return writeback

        identity_handle = _resolve_social_self_identity_handle(state)
        store = self.social_self_store or SocialSelfStore(default_identity=identity_handle)
        current_state = store.load(identity_handle) or SocialSelfState(identity_handle=identity_handle)
        current_state.identity_handle = identity_handle
        owner = SocialSelfOwner(initial_state=current_state, store=store)

        surface_reasons = list(writeback_candidate.get("surface_reasons") or delta.get("surface_reasons") or [])
        counterpart_id = str(
            writeback_candidate.get("counterpart_id")
            or trust_commitment_snapshot.get("counterpart_id")
            or delta.get("counterpart_id")
            or next(
                (
                    item.get("counterpart_id")
                    for item in [*relation_candidates, *repair_candidates]
                    if str(item.get("counterpart_id") or "").strip()
                ),
                state.session_id,
            )
        ).strip()

        relationship_continuity_raw = str(
            trust_commitment_snapshot.get("relationship_continuity")
            or delta.get("relationship_continuity")
            or next(
                (
                    item.get("relationship_continuity")
                    for item in relation_candidates
                    if str(item.get("relationship_continuity") or "").strip()
                ),
                "active",
            )
        ).strip().lower()
        continuity_map = {
            "stable": RelationshipContinuityStatus.ACTIVE,
            "active": RelationshipContinuityStatus.ACTIVE,
            "strained": RelationshipContinuityStatus.STRAINED,
            "repairing": RelationshipContinuityStatus.REPAIRING,
            "paused": RelationshipContinuityStatus.PAUSED,
        }
        continuity_status = continuity_map.get(relationship_continuity_raw, RelationshipContinuityStatus.ACTIVE)

        boundary_mode_raw = str(
            social_policy_hints.get("boundary_mode")
            or writeback_candidate.get("boundary_mode")
            or "cautious"
        ).strip().lower()
        try:
            boundary_mode = SocialBoundaryMode(boundary_mode_raw)
        except ValueError:
            boundary_mode = SocialBoundaryMode.CAUTIOUS

        changed_fields: list[str] = []
        if counterpart_id:
            relationship_event = str(
                next(
                    (
                        item.get("relationship_event")
                        for item in relation_candidates
                        if str(item.get("relationship_event") or "").strip()
                    ),
                    "",
                )
                or writeback_candidate.get("relationship_event")
                or "social_adjustment"
            )
            owner.upsert_relation_memory(
                counterpart_id=counterpart_id,
                relationship_summary=f"proto_self social continuity review: {relationship_event}",
                interaction_role="user",
                continuity_status=continuity_status,
                source_refs=[trace_reference],
            )
            changed_fields.append("relation_memory")

            trust_level = float(trust_commitment_snapshot.get("trust_signal_max") or 0.5)
            trust_level = max(0.0, min(1.0, trust_level))
            trust_delta = float(trust_commitment_snapshot.get("trust_drift") or 0.0)
            owner.set_trust_state(
                counterpart_id=counterpart_id,
                trust_level=trust_level,
                trust_basis=surface_reasons or [str(social_policy_hints.get("trust_bias") or "bounded_social_review")],
                trust_delta=max(-1.0, min(1.0, trust_delta)),
            )
            changed_fields.append("trust_state")

            caution_level = float(trust_commitment_snapshot.get("boundary_caution_max") or 0.0)
            if caution_level <= 0.0:
                caution_level = {
                    SocialBoundaryMode.OPEN: 0.2,
                    SocialBoundaryMode.CAUTIOUS: 0.5,
                    SocialBoundaryMode.FIRM: 0.8,
                    SocialBoundaryMode.REPAIR_ONLY: 0.9,
                }[boundary_mode]
            owner.set_social_boundary(
                counterpart_id=counterpart_id,
                caution_level=max(0.0, min(1.0, caution_level)),
                boundary_mode=boundary_mode,
                reason=f"proto_self_social_boundary:{boundary_mode.value}",
                source_refs=[trace_reference],
            )
            changed_fields.append("social_boundary_state")

        open_commitment_count = int(trust_commitment_snapshot.get("open_commitment_count") or 0)
        breached_commitment_count = int(trust_commitment_snapshot.get("breached_commitment_count") or 0)
        if counterpart_id and (
            open_commitment_count > 0
            or breached_commitment_count > 0
            or social_policy_hints.get("commitment_guard") == "strict"
        ):
            commitment_status = (
                SocialCommitmentStatus.BREACHED
                if breached_commitment_count > 0 or "commitment_breach" in surface_reasons
                else SocialCommitmentStatus.HELD
                if open_commitment_count > 0
                else SocialCommitmentStatus.OPEN
            )
            owner.record_commitment(
                counterpart_id=counterpart_id,
                commitment_id=f"social_commitment:{proto_self_result.get('event_id', 'unknown')}",
                summary="proto_self social commitment review",
                status=commitment_status,
                source_refs=[trace_reference],
            )
            changed_fields.append("commitment_state")

        proposal_count = 0
        for candidate in repair_candidates[:3]:
            repair = owner.propose_repair(
                counterpart_id=str(candidate.get("counterpart_id") or counterpart_id or state.session_id),
                issue_summary=str(
                    candidate.get("reason")
                    or "proto_self social repair candidate"
                ),
                proposed_adjustment={
                    "social_self_delta": delta,
                    "trust_commitment_snapshot": trust_commitment_snapshot,
                    "social_policy_hints": social_policy_hints,
                    "surface_reasons": list(candidate.get("surface_reasons") or surface_reasons),
                },
                justification=f"proto_self social proposal from {trace_reference}",
                source_refs=[trace_reference],
                requested_effects=list(candidate.get("requested_effects") or []),
            )
            owner.set_repair_status(repair.proposal_id, status=SocialRepairProposalStatus.HELD)
            proposal_count += 1
        if proposal_count:
            changed_fields.append("repair_state")

        owner.record_governance_event(
            event_type="social_writeback",
            reference_id=counterpart_id or trace_reference,
            gate_verdict="allow_writeback",
            details={
                "trace_reference": trace_reference,
                "proposal_candidate_count": proposal_count,
                "relation_candidate_count": len(relation_candidates),
                "proposal_only": True,
                "behavioral_authority": "none",
                "surface_reasons": surface_reasons,
            },
        )
        changed_fields.append("governance_ledger")

        try:
            record = owner.persist(
                update_source=str(writeback_candidate.get("source") or "proto_self_v2"),
                trace_reference=trace_reference,
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": sorted(set(changed_fields)),
                    "proposal_count": proposal_count,
                    "relation_candidate_count": len(relation_candidates),
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_reference,
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_reference,
            }
        proto_self_result["social_writeback"] = writeback
        return writeback

    def _apply_embodied_self_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("embodied_self_delta") or {})
        consequence_candidates = list(proto_self_result.get("consequence_update_candidates") or [])
        resource_boundary_snapshot = dict(proto_self_result.get("resource_boundary_snapshot") or {})
        embodied_policy_hints = dict(proto_self_result.get("embodied_policy_hints") or {})
        repair_candidates = list(proto_self_result.get("repair_or_stabilize_proposal_candidates") or [])
        writeback_candidate = dict(proto_self_result.get("embodied_writeback_candidate") or {})
        if (
            not delta
            and not consequence_candidates
            and not resource_boundary_snapshot
            and not writeback_candidate
        ):
            return None

        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        trace_reference = str(
            trace_payload.get("update_packet_hash")
            or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
        )

        if writeback_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": "embodied_writeback_requires_proposal_only"},
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["embodied_writeback"] = writeback
            return writeback
        if writeback_candidate.get("behavioral_authority") not in {None, "none"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "embodied_writeback_behavioral_authority_must_remain_none",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["embodied_writeback"] = writeback
            return writeback
        if writeback_candidate.get("required_gate") not in {None, EMBODIED_WRITEBACK_GATE}:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": "embodied_writeback_requires_formal_gate"},
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["embodied_writeback"] = writeback
            return writeback

        for candidate in [*consequence_candidates[:3], *repair_candidates[:3]]:
            if candidate.get("proposal_discipline") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {"gate_verdict": "reject", "reason": "embodied_candidate_requires_proposal_only"},
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["embodied_writeback"] = writeback
                return writeback
            if candidate.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "embodied_candidate_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["embodied_writeback"] = writeback
                return writeback
            if candidate.get("required_gate") not in {None, EMBODIED_WRITEBACK_GATE}:
                writeback = {
                    "decision": {"gate_verdict": "reject", "reason": "embodied_candidate_requires_formal_gate"},
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["embodied_writeback"] = writeback
                return writeback

        identity_handle = _resolve_embodied_self_identity_handle(state)
        store = self.embodied_self_store or EmbodiedSelfStore(default_identity=identity_handle)
        current_state = store.load(identity_handle) or EmbodiedSelfState(identity_handle=identity_handle)
        current_state.identity_handle = identity_handle
        owner = EmbodiedSelfOwner(initial_state=current_state, store=store)

        action_ref = str(
            writeback_candidate.get("action_ref")
            or resource_boundary_snapshot.get("action_ref")
            or next(
                (
                    item.get("action_ref")
                    for item in consequence_candidates
                    if str(item.get("action_ref") or "").strip()
                ),
                "",
            )
            or "runtime:observe"
        ).strip()
        outcome_type = str(
            resource_boundary_snapshot.get("outcome_type")
            or next(
                (
                    item.get("outcome_type")
                    for item in consequence_candidates
                    if str(item.get("outcome_type") or "").strip()
                ),
                "",
            )
            or "observed"
        ).strip()
        boundary_signal = str(
            resource_boundary_snapshot.get("boundary_signal")
            or embodied_policy_hints.get("boundary_mode")
            or delta.get("boundary_signal")
            or "open"
        ).strip().lower()

        coupling_status_map = {
            "success": EnvironmentCouplingStatus.STABLE,
            "observed": EnvironmentCouplingStatus.STABLE,
            "failure": EnvironmentCouplingStatus.STRAINED,
            "blocked": EnvironmentCouplingStatus.DEGRADED,
            "timeout": EnvironmentCouplingStatus.DEGRADED,
            "error": EnvironmentCouplingStatus.DEGRADED,
        }
        boundary_mode_map = {
            "open": EmbodiedBoundaryPressureMode.STABLE,
            "stable": EmbodiedBoundaryPressureMode.STABLE,
            "guarded": EmbodiedBoundaryPressureMode.GUARDED,
            "pressured": EmbodiedBoundaryPressureMode.PRESSURED,
            "repair_only": EmbodiedBoundaryPressureMode.REPAIR_ONLY,
            "cautious": EmbodiedBoundaryPressureMode.GUARDED,
        }

        changed_fields: list[str] = []
        owner.set_embodied_state(
            resource_slack=float(resource_boundary_snapshot.get("min_resource_slack") or 0.0),
            perceived_load=float(resource_boundary_snapshot.get("perceived_load") or 0.0),
            action_readiness=max(
                0.0,
                min(
                    1.0,
                    float(resource_boundary_snapshot.get("min_resource_slack") or 0.0)
                    + (1.0 - float(resource_boundary_snapshot.get("max_resource_pressure") or 0.0)) * 0.5,
                ),
            ),
            last_action_source="proto_self_v2",
            source_refs=[trace_reference],
        )
        changed_fields.append("embodied_state")

        owner.upsert_environment_coupling(
            coupling_id=action_ref or "runtime:observe",
            coupling_strength=max(
                0.0,
                min(
                    1.0,
                    float(resource_boundary_snapshot.get("max_resource_pressure") or 0.0)
                    + 0.1 * float(resource_boundary_snapshot.get("recent_consequence_count") or 0),
                ),
            ),
            controllability_estimate=max(
                0.0,
                min(
                    1.0,
                    1.0 - float(resource_boundary_snapshot.get("self_world_guard_bias") or 0.0) * 0.5,
                ),
            ),
            recent_outcome_summary=str(
                resource_boundary_snapshot.get("outcome_type")
                or embodied_policy_hints.get("consequence_mode")
                or outcome_type
            ),
            status=coupling_status_map.get(outcome_type.lower(), EnvironmentCouplingStatus.STABLE),
            source_refs=[trace_reference],
        )
        changed_fields.append("environment_coupling_state")

        owner.set_resource_pressure(
            pressure_id="resource:runtime",
            pressure_level=float(resource_boundary_snapshot.get("max_resource_pressure") or 0.0),
            slack_level=float(resource_boundary_snapshot.get("min_resource_slack") or 0.0),
            recovery_bias=1.0 if embodied_policy_hints.get("stabilization_bias") == "elevated" else 0.5,
            source_refs=[trace_reference],
        )
        changed_fields.append("resource_pressure_state")

        owner.set_boundary_pressure(
            boundary_id="self_world",
            pressure_level=float(resource_boundary_snapshot.get("max_boundary_pressure") or 0.0),
            mode=boundary_mode_map.get(boundary_signal, EmbodiedBoundaryPressureMode.STABLE),
            reason=f"proto_self_embodied_boundary:{boundary_signal}",
            source_refs=[trace_reference],
        )
        changed_fields.append("boundary_pressure_state")

        owner.record_action_consequence(
            consequence_id=f"embodied_consequence:{proto_self_result.get('event_id', 'unknown')}",
            action_ref=action_ref or "runtime:observe",
            outcome_type=outcome_type or "observed",
            consequence_summary=str(
                embodied_policy_hints.get("consequence_mode")
                or resource_boundary_snapshot.get("outcome_type")
                or "embodied consequence observed"
            ),
            impact_score=max(
                float(resource_boundary_snapshot.get("max_resource_pressure") or 0.0),
                float(resource_boundary_snapshot.get("max_boundary_pressure") or 0.0),
            ),
            controllability_estimate=max(
                0.0,
                min(
                    1.0,
                    1.0 - float(resource_boundary_snapshot.get("self_world_guard_bias") or 0.0) * 0.4,
                ),
            ),
            source_refs=[trace_reference],
        )
        changed_fields.append("action_consequence_memory")

        owner.set_self_world_boundary_semantics(
            distinction_summary=f"bounded_embodied_boundary:{boundary_signal}",
            guard_bias=float(resource_boundary_snapshot.get("self_world_guard_bias") or 0.0),
            repair_bias=1.0 if embodied_policy_hints.get("stabilization_bias") == "elevated" else 0.5,
            source_refs=[trace_reference],
        )
        changed_fields.append("self_world_boundary_semantics")

        proposal_count = 0
        for idx, candidate in enumerate(repair_candidates[:3], start=1):
            proposal = owner.propose_stabilization(
                proposal_id=f"embodied_proposal:{proto_self_result.get('event_id', 'unknown')}:{idx}",
                target_ref=str(candidate.get("reason") or action_ref or "self_world"),
                issue_summary=str(candidate.get("reason") or "repair_or_stabilize"),
                proposed_adjustment={
                    "embodied_self_delta": delta,
                    "resource_boundary_snapshot": resource_boundary_snapshot,
                    "embodied_policy_hints": embodied_policy_hints,
                    "surface_reasons": list(candidate.get("surface_reasons") or writeback_candidate.get("surface_reasons") or []),
                },
                justification=f"proto_self embodied proposal from {trace_reference}",
                source_refs=[trace_reference],
                requested_effects=list(candidate.get("requested_effects") or []),
            )
            owner.set_proposal_status(proposal.proposal_id, status=EmbodiedProposalStatus.HELD)
            proposal_count += 1
        if proposal_count:
            changed_fields.append("proposal_history")

        owner.record_governance_event(
            event_type="embodied_writeback",
            reference_id=action_ref or trace_reference,
            gate_verdict="allow_writeback",
            details={
                "trace_reference": trace_reference,
                "proposal_candidate_count": proposal_count,
                "consequence_candidate_count": len(consequence_candidates),
                "proposal_only": True,
                "behavioral_authority": "none",
                "surface_reasons": list(writeback_candidate.get("surface_reasons") or delta.get("surface_reasons") or []),
            },
        )
        changed_fields.append("governance_ledger")

        try:
            record = owner.persist(
                update_source=str(writeback_candidate.get("source") or "proto_self_v2"),
                trace_reference=trace_reference,
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": sorted(set(changed_fields)),
                    "proposal_count": proposal_count,
                    "consequence_candidate_count": len(consequence_candidates),
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_reference,
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_reference,
            }
        proto_self_result["embodied_writeback"] = writeback
        return writeback

    def _apply_selfhood_integration_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("self_integration_delta") or {})
        priority_snapshot = dict(proto_self_result.get("cross_axis_priority_snapshot") or {})
        conflict_snapshot = dict(proto_self_result.get("proposal_conflict_snapshot") or {})
        policy_hints = dict(proto_self_result.get("integrated_policy_hints") or {})
        integrated_tendency = dict(proto_self_result.get("integrated_tendency_proposal") or {})
        axis_hints = dict(proto_self_result.get("axis_arbitration_hints") or {})
        audit_entries = list(proto_self_result.get("integration_audit_entries") or [])
        writeback_candidate = dict(proto_self_result.get("self_integration_writeback_candidate") or {})
        if (
            not delta
            and not priority_snapshot
            and not conflict_snapshot
            and not integrated_tendency
            and not writeback_candidate
        ):
            return None

        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        trace_reference = str(
            trace_payload.get("update_packet_hash")
            or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
        )

        if writeback_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "self_integration_writeback_requires_proposal_only",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["selfhood_integration_writeback"] = writeback
            return writeback
        if writeback_candidate.get("behavioral_authority") not in {None, "none"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "self_integration_writeback_behavioral_authority_must_remain_none",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["selfhood_integration_writeback"] = writeback
            return writeback
        if writeback_candidate.get("required_gate") not in {None, SELFHOOD_INTEGRATION_WRITEBACK_GATE}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "self_integration_writeback_requires_formal_gate",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["selfhood_integration_writeback"] = writeback
            return writeback
        if integrated_tendency:
            if integrated_tendency.get("proposal_discipline") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "integrated_tendency_requires_proposal_only",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["selfhood_integration_writeback"] = writeback
                return writeback
            if integrated_tendency.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "integrated_tendency_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["selfhood_integration_writeback"] = writeback
                return writeback
            if integrated_tendency.get("required_gate") not in {None, SELFHOOD_INTEGRATION_WRITEBACK_GATE}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "integrated_tendency_requires_formal_gate",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["selfhood_integration_writeback"] = writeback
                return writeback
        for axis_name, hint in axis_hints.items():
            if not bool(hint.get("advisory_only", True)):
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": f"axis_arbitration_hint_must_remain_advisory:{axis_name}",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["selfhood_integration_writeback"] = writeback
                return writeback

        identity_handle = _resolve_selfhood_integration_identity_handle(state)
        store = self.selfhood_integration_store or SelfhoodIntegrationStore(default_identity=identity_handle)
        current_state = store.load(identity_handle) or SelfhoodIntegrationState(identity_handle=identity_handle)
        current_state.identity_handle = identity_handle
        owner = SelfhoodIntegrationOwner(initial_state=current_state, store=store)

        selected_priority_raw = str(
            priority_snapshot.get("selected_priority")
            or writeback_candidate.get("selected_priority")
            or policy_hints.get("selected_priority")
            or delta.get("selected_priority")
            or "review"
        ).strip().lower()
        try:
            selected_priority = SelfhoodArbitrationPriority(selected_priority_raw)
        except ValueError:
            selected_priority = SelfhoodArbitrationPriority.REVIEW

        dominant_pressure_axis = str(
            policy_hints.get("dominant_pressure_axis")
            or writeback_candidate.get("dominant_pressure_axis")
            or delta.get("dominant_pressure_axis")
            or "stability"
        ).strip() or "stability"

        highest_conflict_raw = str(
            conflict_snapshot.get("highest_severity")
            or writeback_candidate.get("conflict_severity")
            or policy_hints.get("conflict_severity")
            or "none"
        ).strip().lower()
        try:
            highest_conflict = SelfhoodConflictSeverity(highest_conflict_raw)
        except ValueError:
            highest_conflict = SelfhoodConflictSeverity.NONE

        conflict_count = int(conflict_snapshot.get("conflict_count") or 0)
        active_axes = list(
            priority_snapshot.get("active_axes")
            or policy_hints.get("active_axes")
            or writeback_candidate.get("active_axes")
            or []
        )
        source_refs = list(
            delta.get("surface_reasons")
            or priority_snapshot.get("upstream_pressure_sources")
            or conflict_snapshot.get("source_refs")
            or []
        )
        if trace_reference not in source_refs:
            source_refs.append(trace_reference)

        owner.set_integration_state(
            posture=selected_priority,
            dominant_pressure_axis=dominant_pressure_axis,
            stability_bias=float(policy_hints.get("stability_bias") or delta.get("stability_bias") or 0.5),
            integration_confidence=float(delta.get("integration_confidence") or 0.5),
            active_axis_count=max(0, min(8, int(delta.get("active_axis_count") or len(active_axes)))),
            rationale_summary=str(
                integrated_tendency.get("justification")
                or priority_snapshot.get("priority_reason")
                or "bounded_cross_axis_integration"
            ),
            source_refs=source_refs,
        )
        owner.set_cross_axis_priority_state(
            selected_priority=selected_priority,
            stabilize_weight=float(priority_snapshot.get("stabilize_weight") or 0.0),
            conserve_weight=float(priority_snapshot.get("conserve_weight") or 0.0),
            guard_weight=float(priority_snapshot.get("guard_weight") or 0.0),
            review_weight=float(priority_snapshot.get("review_weight") or 0.0),
            repair_weight=float(priority_snapshot.get("repair_weight") or 0.0),
            grow_weight=float(priority_snapshot.get("grow_weight") or 0.0),
            reflective_modifier=float(priority_snapshot.get("reflective_modifier") or 0.0),
            priority_reason=str(priority_snapshot.get("priority_reason") or "bounded_cross_axis_integration"),
            upstream_pressure_sources=list(priority_snapshot.get("upstream_pressure_sources") or source_refs),
            source_refs=source_refs,
        )
        owner.set_proposal_conflict_state(
            highest_severity=highest_conflict,
            conflict_count=conflict_count,
            unresolved_conflict_refs=list(conflict_snapshot.get("unresolved_conflict_refs") or []),
            blocked_axes=list(conflict_snapshot.get("blocked_axes") or []),
            resolution_posture=SelfhoodArbitrationPriority.REVIEW
            if conflict_count
            else selected_priority,
            source_refs=source_refs,
        )

        stabilize_weight = float(priority_snapshot.get("stabilize_weight") or 0.62)
        grow_weight = float(priority_snapshot.get("grow_weight") or max(0.0, 1.0 - stabilize_weight))
        owner.set_stabilize_explore_balance(
            stabilize_weight=stabilize_weight,
            explore_weight=grow_weight,
            preferred_pole="stabilize" if selected_priority in {"stabilize", "conserve", "guard", "review"} else "explore",
            rationale=str(priority_snapshot.get("priority_reason") or "stability-first arbitration balance"),
            source_refs=source_refs,
        )
        repair_weight = float(priority_snapshot.get("repair_weight") or 0.58)
        progress_weight = max(float(priority_snapshot.get("grow_weight") or 0.0), float(priority_snapshot.get("review_weight") or 0.0))
        owner.set_repair_progress_balance(
            repair_weight=repair_weight,
            progress_weight=progress_weight,
            preferred_pole="repair" if selected_priority in {"repair", "review"} else "progress",
            rationale="bounded repair-progress arbitration under stability-first policy",
            source_refs=source_refs,
        )
        social_weight = 0.62 if selected_priority == SelfhoodArbitrationPriority.REPAIR else 0.44
        if "social_self" in active_axes and selected_priority not in {
            SelfhoodArbitrationPriority.STABILIZE,
            SelfhoodArbitrationPriority.CONSERVE,
            SelfhoodArbitrationPriority.GUARD,
        }:
            social_weight = 0.55
        boundary_weight = max(0.0, min(1.0, 1.0 - social_weight))
        owner.set_social_boundary_balance(
            social_weight=social_weight,
            boundary_weight=boundary_weight,
            preferred_pole="boundary" if selected_priority in {"stabilize", "conserve", "guard", "review"} else "social",
            rationale="bounded social-boundary arbitration under stability-first policy",
            source_refs=source_refs,
        )

        if integrated_tendency:
            owner.propose_integrated_tendency(
                proposal_id=str(
                    integrated_tendency.get("proposal_id")
                    or f"self_integration:{selected_priority.value}:{current_state.owner_revision}:{len(source_refs)}"
                ),
                tendency_label=str(
                    integrated_tendency.get("tendency_label")
                    or f"{selected_priority.value}_first_integration"
                ),
                priority_mode=selected_priority,
                proposed_effects=dict(integrated_tendency.get("proposed_effects") or {}),
                justification=str(
                    integrated_tendency.get("justification")
                    or priority_snapshot.get("priority_reason")
                    or "bounded_cross_axis_integration"
                ),
                requested_effects=list(integrated_tendency.get("requested_effects") or []),
                source_refs=list(integrated_tendency.get("source_refs") or source_refs),
            )
            owner.set_integrated_tendency_status(status=SelfhoodIntegratedProposalStatus.HELD)

        for axis_name, hint in axis_hints.items():
            owner.upsert_axis_arbitration_hint(
                axis_name=str(axis_name),
                recommendation=str(hint.get("recommendation") or "bounded_review"),
                priority_weight=float(hint.get("priority_weight") or 0.0),
                guardrail_summary=str(hint.get("guardrail_summary") or "advisory_only_no_upstream_owner_mutation"),
                source_refs=list(hint.get("source_refs") or source_refs),
            )

        for audit_entry in audit_entries[:12]:
            owner.record_integration_event(
                event_type=str(audit_entry.get("kind") or "integration_signal"),
                reference_id=str(
                    audit_entry.get("conflict_ref")
                    or audit_entry.get("selected_priority")
                    or trace_reference
                ),
                gate_verdict="allow_writeback",
                details={k: v for k, v in audit_entry.items() if k != "kind"},
            )
        owner.record_integration_event(
            event_type="self_integration_writeback",
            reference_id=str(
                integrated_tendency.get("proposal_id")
                or writeback_candidate.get("selected_priority")
                or trace_reference
            ),
            gate_verdict="allow_writeback",
            details={
                "trace_reference": trace_reference,
                "proposal_only": True,
                "behavioral_authority": "none",
                "active_axis_count": len(active_axes),
                "selected_priority": selected_priority.value,
            },
        )

        changed_fields = [
            "integration_state",
            "cross_axis_priority_state",
            "proposal_conflict_state",
            "stabilize_explore_balance",
            "repair_progress_balance",
            "social_boundary_balance",
            "axis_arbitration_hints",
            "integration_ledger",
        ]
        if integrated_tendency:
            changed_fields.append("integrated_tendency_proposal")

        try:
            record = owner.persist(
                update_source=str(writeback_candidate.get("source") or "proto_self_v2"),
                trace_reference=trace_reference,
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": sorted(set(changed_fields)),
                    "active_axis_count": len(active_axes),
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_reference,
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_reference,
            }
        proto_self_result["selfhood_integration_writeback"] = writeback
        return writeback

    def _apply_initiative_self_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("initiative_self_delta") or {})
        proposal_candidates = list(proto_self_result.get("initiative_proposal_candidates") or [])
        commitment_snapshot = dict(proto_self_result.get("commitment_execution_snapshot") or {})
        initiative_policy_hints = dict(proto_self_result.get("initiative_policy_hints") or {})
        host_candidate = dict(proto_self_result.get("host_proactive_candidate") or {})
        audit_entries = list(proto_self_result.get("initiative_audit_entries") or [])
        writeback_candidate = dict(proto_self_result.get("initiative_writeback_candidate") or {})
        if (
            not delta
            and not proposal_candidates
            and not commitment_snapshot
            and not host_candidate
            and not writeback_candidate
        ):
            return None

        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        trace_reference = str(
            trace_payload.get("update_packet_hash")
            or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
        )

        if writeback_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "initiative_writeback_requires_proposal_only",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["initiative_writeback"] = writeback
            return writeback
        if writeback_candidate.get("behavioral_authority") not in {None, "none"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "initiative_writeback_behavioral_authority_must_remain_none",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["initiative_writeback"] = writeback
            return writeback
        if writeback_candidate.get("required_gate") not in {None, INITIATIVE_WRITEBACK_GATE}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "initiative_writeback_requires_formal_gate",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["initiative_writeback"] = writeback
            return writeback

        for candidate in proposal_candidates[:3]:
            if candidate.get("effect_scope") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "initiative_candidate_requires_proposal_only_scope",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_writeback"] = writeback
                return writeback
            if candidate.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "initiative_candidate_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_writeback"] = writeback
                return writeback
            if candidate.get("required_gate") not in {None, INITIATIVE_WRITEBACK_GATE}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "initiative_candidate_requires_formal_gate",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_writeback"] = writeback
                return writeback

        if host_candidate:
            if host_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "host_proactive_candidate_requires_proposal_only",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_writeback"] = writeback
                return writeback
            if host_candidate.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "host_proactive_candidate_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_writeback"] = writeback
                return writeback
            if host_candidate.get("required_gate") not in {None, INITIATIVE_WRITEBACK_GATE}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "host_proactive_candidate_requires_formal_gate",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_writeback"] = writeback
                return writeback

        identity_handle = _resolve_initiative_self_identity_handle(state)
        store = self.initiative_self_store or InitiativeSelfStore(default_identity=identity_handle)
        current_state = store.load(identity_handle) or InitiativeSelfState(identity_handle=identity_handle)
        current_state.identity_handle = identity_handle
        owner = InitiativeSelfOwner(initial_state=current_state, store=store)

        selected_priority_raw = str(
            commitment_snapshot.get("selected_priority")
            or initiative_policy_hints.get("initiative_bias")
            or delta.get("selected_priority")
            or "review"
        ).strip().lower()
        try:
            selected_priority = InitiativePriority(selected_priority_raw)
        except ValueError:
            selected_priority = InitiativePriority.REVIEW

        commitment_mode = str(
            commitment_snapshot.get("commitment_mode")
            or initiative_policy_hints.get("commitment_mode")
            or "idle"
        ).strip().lower()
        if commitment_mode == "blocked":
            continuity_status = InitiativeCommitmentContinuityStatus.BLOCKED
        elif commitment_mode == "carry_forward":
            continuity_status = InitiativeCommitmentContinuityStatus.ACTIVE
        elif commitment_mode == "idle":
            continuity_status = InitiativeCommitmentContinuityStatus.DEFERRED
        else:
            continuity_status = InitiativeCommitmentContinuityStatus.ACTIVE

        reserve_bias = str(initiative_policy_hints.get("reserve_bias") or "bounded")
        recent_delivery_status = str(commitment_snapshot.get("recent_delivery_status") or "")
        continuity_confidence = float(commitment_snapshot.get("continuity_confidence") or 0.5)
        active_commitments_count = int(commitment_snapshot.get("active_commitments_count") or 0)
        blocked_commitments_count = int(commitment_snapshot.get("blocked_commitments_count") or 0)
        source_refs = list(delta.get("surface_reasons") or [])
        if trace_reference not in source_refs:
            source_refs.append(trace_reference)

        initiative_pressure = 0.0
        if "initiative_pressure" in delta:
            initiative_pressure = float(delta.get("initiative_pressure") or 0.0)
        elif active_commitments_count > 0:
            initiative_pressure = 0.72
        elif commitment_mode == "blocked":
            initiative_pressure = 0.58
        initiative_pressure = max(0.0, min(1.0, initiative_pressure))

        carryover_bias = 0.0
        if "commitment_carryover_bias" in delta:
            carryover_bias = float(delta.get("commitment_carryover_bias") or 0.0)
        elif commitment_mode in {"carry_forward", "blocked"}:
            carryover_bias = 0.74
        carryover_bias = max(0.0, min(1.0, carryover_bias))

        delivery_sensitivity = 0.0
        if "recent_delivery_sensitivity" in delta:
            delivery_sensitivity = float(delta.get("recent_delivery_sensitivity") or 0.0)
        elif recent_delivery_status in {"failed", "blocked"}:
            delivery_sensitivity = 0.68
        delivery_sensitivity = max(0.0, min(1.0, delivery_sensitivity))

        owner.set_initiative_state(
            dominant_mode=selected_priority,
            initiative_pressure=initiative_pressure,
            commitment_carryover_bias=carryover_bias,
            recent_delivery_sensitivity=delivery_sensitivity,
            rationale_summary=str(
                proposal_candidates[0].get("justification")
                if proposal_candidates
                else "bounded_initiative_review"
            ),
            source_refs=source_refs,
        )
        owner.set_initiative_priority_state(
            selected_priority=selected_priority,
            hold_weight=1.0 if selected_priority == InitiativePriority.HOLD else 0.2,
            review_weight=1.0 if selected_priority == InitiativePriority.REVIEW else 0.35,
            prepare_weight=1.0 if selected_priority == InitiativePriority.PREPARE else 0.3,
            carry_forward_weight=1.0 if selected_priority == InitiativePriority.CARRY_FORWARD else 0.25,
            schedule_weight=1.0 if selected_priority == InitiativePriority.SCHEDULE else 0.2,
            priority_reason=str(
                proposal_candidates[0].get("justification")
                if proposal_candidates
                else "bounded_initiative_priority"
            ),
            upstream_pressure_sources=source_refs,
            source_refs=source_refs,
        )
        owner.set_commitment_continuity_state(
            status=continuity_status,
            active_commitments_count=active_commitments_count,
            carried_commitment_refs=list(commitment_snapshot.get("carried_commitment_refs") or []),
            blocked_commitment_refs=[f"blocked:{idx}" for idx in range(blocked_commitments_count)],
            continuity_confidence=continuity_confidence,
            carryover_summary=str(
                commitment_snapshot.get("commitment_mode")
                or initiative_policy_hints.get("continuity_mode")
                or "bounded_commitment_continuity"
            ),
            source_refs=source_refs,
        )

        proposal_count = 0
        for candidate in proposal_candidates[:3]:
            owner.propose_initiative(
                proposal_id=str(candidate.get("proposal_id") or f"initiative:{selected_priority.value}"),
                proposal_label=str(candidate.get("proposal_label") or "bounded_initiative_review"),
                priority_mode=selected_priority,
                proposed_effects=dict(candidate.get("proposed_effects") or {}),
                justification=str(candidate.get("justification") or "bounded_initiative_review"),
                source_refs=list(candidate.get("source_refs") or source_refs),
                requested_effects=list(candidate.get("requested_effects") or []),
            )
            owner.set_initiative_proposal_status(status=InitiativeProposalStatus.HELD)
            proposal_count += 1

        host_candidate_present = False
        if host_candidate:
            owner.set_host_proactive_candidate(
                candidate_id=str(host_candidate.get("candidate_id") or f"host_candidate:{selected_priority.value}"),
                candidate_label=str(
                    host_candidate.get("candidate_label") or "governed_host_proactive_followup"
                ),
                continuity_basis=str(
                    host_candidate.get("continuity_basis")
                    or commitment_snapshot.get("commitment_mode")
                    or "bounded_continuity_review"
                ),
                host_lane_hint=str(host_candidate.get("host_lane_hint") or "host_proactive_outbox"),
                source_refs=list(host_candidate.get("source_refs") or source_refs),
                requested_effects=list(host_candidate.get("requested_effects") or []),
            )
            owner.set_host_proactive_candidate_status(status=HostProactiveCandidateStatus.HELD)
            host_candidate_present = True

        for audit_entry in audit_entries[:10]:
            owner.record_initiative_event(
                event_type=str(audit_entry.get("entry_type") or "initiative_signal"),
                reference_id=str(
                    audit_entry.get("selected_priority")
                    or audit_entry.get("host_proactive_mode")
                    or trace_reference
                ),
                gate_verdict="allow_writeback",
                details={k: v for k, v in audit_entry.items() if k != "entry_type"},
            )
        owner.record_initiative_event(
            event_type="initiative_writeback",
            reference_id=str(
                proposal_candidates[0].get("proposal_id")
                if proposal_candidates
                else host_candidate.get("candidate_id")
                if host_candidate
                else trace_reference
            ),
            gate_verdict="allow_writeback",
            details={
                "trace_reference": trace_reference,
                "proposal_only": True,
                "behavioral_authority": "none",
                "proposal_count": proposal_count,
                "host_proactive_candidate_present": host_candidate_present,
                "selected_priority": selected_priority.value,
                "reserve_bias": reserve_bias,
            },
        )

        changed_fields = [
            "initiative_state",
            "initiative_priority_state",
            "commitment_continuity_state",
            "initiative_ledger",
        ]
        if proposal_count:
            changed_fields.append("initiative_proposal_candidate")
        if host_candidate_present:
            changed_fields.append("host_proactive_candidate")

        try:
            record = owner.persist(
                update_source=str(writeback_candidate.get("source") or "proto_self_v2"),
                trace_reference=trace_reference,
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": sorted(set(changed_fields)),
                    "proposal_count": proposal_count,
                    "host_proactive_candidate_present": host_candidate_present,
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_reference,
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_reference,
            }
        proto_self_result["initiative_writeback"] = writeback
        return writeback

    def _apply_initiative_realization_writeback(
        self,
        *,
        proto_self_result: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Optional[Dict[str, Any]]:
        delta = dict(proto_self_result.get("initiative_realization_delta") or {})
        fulfillment_candidates = list(proto_self_result.get("commitment_fulfillment_candidates") or [])
        readiness_snapshot = dict(proto_self_result.get("delivery_readiness_snapshot") or {})
        host_lane_hints = list(proto_self_result.get("host_lane_hints") or [])
        controlled_delivery_candidate = dict(proto_self_result.get("controlled_delivery_candidate") or {})
        audit_entries = list(proto_self_result.get("initiative_realization_audit_entries") or [])
        writeback_candidate = dict(proto_self_result.get("initiative_realization_writeback_candidate") or {})
        if (
            not delta
            and not fulfillment_candidates
            and not readiness_snapshot
            and not controlled_delivery_candidate
            and not writeback_candidate
        ):
            return None

        trace_payload = dict(proto_self_result.get("trace_payload") or {})
        trace_reference = str(
            trace_payload.get("update_packet_hash")
            or f"proto_self:{proto_self_result.get('event_id', 'unknown')}"
        )

        if writeback_candidate.get("proposal_discipline") not in {None, "proposal_only"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "initiative_realization_writeback_requires_proposal_only",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["initiative_realization_writeback"] = writeback
            return writeback
        if writeback_candidate.get("behavioral_authority") not in {None, "none"}:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "initiative_realization_writeback_behavioral_authority_must_remain_none",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["initiative_realization_writeback"] = writeback
            return writeback
        if writeback_candidate.get("required_gate") not in {
            None,
            INITIATIVE_REALIZATION_WRITEBACK_GATE,
        }:
            writeback = {
                "decision": {
                    "gate_verdict": "reject",
                    "reason": "initiative_realization_writeback_requires_formal_gate",
                },
                "record": None,
                "trace_reference": trace_reference,
            }
            proto_self_result["initiative_realization_writeback"] = writeback
            return writeback

        if controlled_delivery_candidate:
            if controlled_delivery_candidate.get("effect_scope") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "controlled_delivery_candidate_requires_proposal_only_scope",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_realization_writeback"] = writeback
                return writeback
            if controlled_delivery_candidate.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "controlled_delivery_candidate_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_realization_writeback"] = writeback
                return writeback
            if controlled_delivery_candidate.get("required_gate") not in {
                None,
                INITIATIVE_REALIZATION_WRITEBACK_GATE,
            }:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "controlled_delivery_candidate_requires_formal_gate",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_realization_writeback"] = writeback
                return writeback

        for candidate in fulfillment_candidates[:3]:
            if candidate.get("effect_scope") not in {None, "proposal_only"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "initiative_realization_candidate_requires_proposal_only_scope",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_realization_writeback"] = writeback
                return writeback
            if candidate.get("behavioral_authority") not in {None, "none"}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "initiative_realization_candidate_behavioral_authority_must_remain_none",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_realization_writeback"] = writeback
                return writeback
            if candidate.get("required_gate") not in {None, INITIATIVE_REALIZATION_WRITEBACK_GATE}:
                writeback = {
                    "decision": {
                        "gate_verdict": "reject",
                        "reason": "initiative_realization_candidate_requires_formal_gate",
                    },
                    "record": None,
                    "trace_reference": trace_reference,
                }
                proto_self_result["initiative_realization_writeback"] = writeback
                return writeback

        identity_handle = _resolve_initiative_realization_identity_handle(state)
        store = self.initiative_realization_store or InitiativeRealizationStore(
            default_identity=identity_handle
        )
        current_state = store.load(identity_handle) or InitiativeRealizationState(identity_handle=identity_handle)
        current_state.identity_handle = identity_handle
        owner = InitiativeRealizationOwner(initial_state=current_state, store=store)

        selected_mode_raw = str(
            readiness_snapshot.get("selected_lane")
            or delta.get("selected_lane")
            or delta.get("dominant_mode")
            or "review"
        ).strip().lower()
        try:
            selected_mode = RealizationMode(selected_mode_raw)
        except ValueError:
            selected_mode = RealizationMode.REVIEW

        fulfillment_status_raw = str(
            readiness_snapshot.get("fulfillment_status")
            or delta.get("fulfillment_status")
            or "active"
        ).strip().lower()
        status_map = {
            "active": CommitmentFulfillmentStatus.ACTIVE,
            "held": CommitmentFulfillmentStatus.HELD,
            "ready": CommitmentFulfillmentStatus.READY,
            "blocked": CommitmentFulfillmentStatus.BLOCKED,
            "fulfilled": CommitmentFulfillmentStatus.FULFILLED,
            "failed": CommitmentFulfillmentStatus.FAILED,
        }
        fulfillment_status = status_map.get(fulfillment_status_raw, CommitmentFulfillmentStatus.ACTIVE)

        source_refs = list(delta.get("surface_reasons") or [])
        if trace_reference not in source_refs:
            source_refs.append(trace_reference)

        owner.set_realization_state(
            dominant_mode=selected_mode,
            realization_pressure=max(0.0, min(1.0, float(delta.get("realization_pressure") or 0.0))),
            fulfillment_readiness=max(
                0.0,
                min(
                    1.0,
                    float(
                        readiness_snapshot.get("delivery_readiness")
                        or delta.get("fulfillment_readiness")
                        or 0.0
                    ),
                ),
            ),
            hold_bias=max(0.0, min(1.0, float(delta.get("hold_bias") or 0.0))),
            failure_recovery_bias=max(
                0.0, min(1.0, float(delta.get("failure_recovery_bias") or 0.0))
            ),
            rationale_summary=str(
                delta.get("rationale_summary")
                or readiness_snapshot.get("lane_reason")
                or "bounded_realization_review"
            ),
            source_refs=source_refs,
        )
        owner.set_delivery_readiness_state(
            selected_lane=selected_mode,
            hold_weight=max(0.0, min(1.0, float(delta.get("hold_weight") or 0.0))),
            review_weight=max(0.0, min(1.0, float(delta.get("review_weight") or 0.0))),
            prepare_weight=max(0.0, min(1.0, float(delta.get("prepare_weight") or 0.0))),
            mediate_weight=max(0.0, min(1.0, float(delta.get("mediate_weight") or 0.0))),
            fulfill_weight=max(0.0, min(1.0, float(delta.get("fulfill_weight") or 0.0))),
            lane_reason=str(readiness_snapshot.get("lane_reason") or "bounded_realization_lane"),
            host_lane_hints=host_lane_hints,
            source_refs=source_refs,
        )
        owner.set_commitment_fulfillment_state(
            status=fulfillment_status,
            active_commitments_count=int(delta.get("active_commitments_count") or 0),
            ready_commitments_count=int(delta.get("ready_commitments_count") or 0),
            realized_commitment_refs=list(delta.get("realized_commitment_refs") or []),
            blocked_commitment_refs=list(delta.get("blocked_commitment_refs") or []),
            continuity_confidence=max(
                0.0,
                min(1.0, float(delta.get("continuity_confidence") or 0.0)),
            ),
            fulfillment_summary=str(
                delta.get("fulfillment_summary")
                or readiness_snapshot.get("readiness_basis")
                or "bounded_commitment_fulfillment"
            ),
            source_refs=source_refs,
        )

        proposal_count = 0
        for candidate in fulfillment_candidates[:3]:
            candidate_mode_raw = str(candidate.get("selected_mode") or selected_mode.value).strip().lower()
            try:
                candidate_mode = RealizationMode(candidate_mode_raw)
            except ValueError:
                candidate_mode = selected_mode
            owner.propose_realization(
                candidate_id=str(candidate.get("candidate_id") or f"realization:{candidate_mode.value}"),
                candidate_label=str(candidate.get("candidate_label") or "bounded_realization_review"),
                selected_mode=candidate_mode,
                proposed_effects=dict(candidate.get("proposed_effects") or {}),
                justification=str(candidate.get("justification") or "bounded_realization_review"),
                source_refs=list(candidate.get("source_refs") or source_refs),
                requested_effects=list(candidate.get("requested_effects") or []),
            )
            owner.set_initiative_realization_candidate_status(status=RealizationProposalStatus.HELD)
            proposal_count += 1

        controlled_delivery_present = False
        if controlled_delivery_candidate:
            owner.set_controlled_delivery_candidate(
                candidate_id=str(
                    controlled_delivery_candidate.get("candidate_id")
                    or f"controlled_delivery:{selected_mode.value}"
                ),
                candidate_label=str(
                    controlled_delivery_candidate.get("candidate_label")
                    or "governed_controlled_delivery_review"
                ),
                readiness_basis=str(
                    controlled_delivery_candidate.get("readiness_basis")
                    or readiness_snapshot.get("readiness_basis")
                    or "bounded_delivery_readiness"
                ),
                delivery_readiness=max(
                    0.0,
                    min(1.0, float(controlled_delivery_candidate.get("delivery_readiness") or 0.0)),
                ),
                host_lane_hint=str(
                    controlled_delivery_candidate.get("host_lane_hint")
                    or (host_lane_hints[0] if host_lane_hints else "host_proactive_outbox")
                ),
                source_refs=list(controlled_delivery_candidate.get("source_refs") or source_refs),
                requested_effects=list(controlled_delivery_candidate.get("requested_effects") or []),
            )
            owner.set_controlled_delivery_candidate_status(status=ControlledDeliveryCandidateStatus.HELD)
            controlled_delivery_present = True

        for audit_entry in audit_entries[:10]:
            owner.record_realization_event(
                event_type=str(audit_entry.get("entry_type") or "initiative_realization_signal"),
                reference_id=str(
                    audit_entry.get("selected_lane")
                    or audit_entry.get("candidate_id")
                    or trace_reference
                ),
                gate_verdict="allow_writeback",
                details={k: v for k, v in audit_entry.items() if k != "entry_type"},
            )
        owner.record_realization_event(
            event_type="initiative_realization_writeback",
            reference_id=str(
                fulfillment_candidates[0].get("candidate_id")
                if fulfillment_candidates
                else controlled_delivery_candidate.get("candidate_id")
                if controlled_delivery_candidate
                else trace_reference
            ),
            gate_verdict="allow_writeback",
            details={
                "trace_reference": trace_reference,
                "proposal_only": True,
                "behavioral_authority": "none",
                "proposal_count": proposal_count,
                "controlled_delivery_present": controlled_delivery_present,
                "selected_lane": selected_mode.value,
            },
        )

        changed_fields = [
            "realization_state",
            "delivery_readiness_state",
            "commitment_fulfillment_state",
            "realization_ledger",
        ]
        if proposal_count:
            changed_fields.append("initiative_realization_candidate")
        if controlled_delivery_present:
            changed_fields.append("controlled_delivery_candidate")

        try:
            record = owner.persist(
                update_source=str(writeback_candidate.get("source") or "proto_self_v2"),
                trace_reference=trace_reference,
            )
            writeback = {
                "decision": {
                    "gate_verdict": "allow_writeback",
                    "changed_fields": sorted(set(changed_fields)),
                    "proposal_count": proposal_count,
                    "controlled_delivery_present": controlled_delivery_present,
                },
                "record": {
                    "revision_id": record.revision_id,
                    "model_version": record.model_version,
                    "trace_reference": record.trace_reference,
                    "state_hash": record.state_hash,
                },
                "trace_reference": trace_reference,
            }
        except Exception as exc:
            writeback = {
                "decision": {"gate_verdict": "reject", "reason": str(exc)},
                "record": None,
                "trace_reference": trace_reference,
            }
        proto_self_result["initiative_realization_writeback"] = writeback
        return writeback

    def process_ingress(
        self,
        *,
        session_id: str,
        turn_id: str,
        source: str,
        user_input: str,
        state: RuntimeV2State,
        evidence_collector: Optional[Any] = None,
    ) -> None:
        proto_self_event = build_proto_self_ingress_event(
            session_id=session_id,
            turn_id=turn_id,
            source=source,
            user_input=user_input,
            state=state,
            self_model_store=self.self_model_store,
            endogenous_drive_store=self.endogenous_drive_store,
            reflective_self_store=self.reflective_self_store,
            developmental_self_store=self.developmental_self_store,
            social_self_store=self.social_self_store,
            embodied_self_store=self.embodied_self_store,
            selfhood_integration_store=self.selfhood_integration_store,
            initiative_self_store=self.initiative_self_store,
            initiative_realization_store=self.initiative_realization_store,
        )
        proto_self_result = normalize_chat_subject_surface(self.adapter.handle_event(proto_self_event))
        writeback = self._apply_self_model_writeback(proto_self_result=proto_self_result, state=state)
        endogenous_drive_writeback = self._apply_endogenous_drive_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        reflective_self_writeback = self._apply_reflective_self_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        developmental_writeback = self._apply_developmental_self_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        social_writeback = self._apply_social_self_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        embodied_writeback = self._apply_embodied_self_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        selfhood_integration_writeback = self._apply_selfhood_integration_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        initiative_writeback = self._apply_initiative_self_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        initiative_realization_writeback = self._apply_initiative_realization_writeback(
            proto_self_result=proto_self_result,
            state=state,
        )
        collector = self._resolve_collector(evidence_collector)
        if collector is not None:
            collector.capture_normalized_event(proto_self_event)
            collector.capture_openemotion_result(proto_self_result)
        self._capture_trace_in_ledger_or_bridge(
            proto_self_result=proto_self_result,
            collector=collector,
            bridge_stage="ingress_kernel_trace",
        )
        shadow_h1 = _extract_shadow_h1_telemetry(proto_self_result)
        state.proto_self_context = {
            "subject_profile": proto_self_result.get("subject_profile"),
            "policy_hint": proto_self_result.get("policy_hint"),
            "response_tendency": proto_self_result.get("response_tendency"),
            "reflection_note": proto_self_result.get("reflection_note"),
            "candidate_actions": proto_self_result.get("candidate_actions") or [],
            "governor_hint": (proto_self_result.get("policy_hint") or {}).get("governor_hint"),
            "self_model_delta": proto_self_result.get("self_model_delta") or {},
            "self_model_writeback": writeback,
            "endogenous_drive_delta": proto_self_result.get("endogenous_drive_delta") or {},
            "endogenous_drive_writeback": endogenous_drive_writeback,
            "drive_state_snapshot": proto_self_result.get("drive_state_snapshot") or {},
            "priority_snapshot": proto_self_result.get("priority_snapshot") or {},
            "candidate_bias_terms": proto_self_result.get("candidate_bias_terms") or {},
            "self_maintenance_candidate": proto_self_result.get("self_maintenance_candidate"),
            "reflective_self_delta": proto_self_result.get("reflective_self_delta") or {},
            "revision_proposal_candidates": proto_self_result.get("revision_proposal_candidates") or [],
            "confidence_adjustment_hints": proto_self_result.get("confidence_adjustment_hints") or {},
            "maintenance_priority_hints": proto_self_result.get("maintenance_priority_hints") or {},
            "reflection_writeback_candidate": proto_self_result.get("reflection_writeback_candidate"),
            "reflective_self_writeback": reflective_self_writeback,
            "developmental_self_delta": proto_self_result.get("developmental_self_delta") or {},
            "developmental_proposal_candidates": proto_self_result.get("developmental_proposal_candidates") or [],
            "developmental_continuity_snapshot": proto_self_result.get("developmental_continuity_snapshot") or {},
            "developmental_priority_hints": proto_self_result.get("developmental_priority_hints") or {},
            "developmental_audit_entries": proto_self_result.get("developmental_audit_entries") or [],
            "developmental_writeback_candidate": proto_self_result.get("developmental_writeback_candidate"),
            "developmental_writeback": developmental_writeback,
            "social_self_delta": proto_self_result.get("social_self_delta") or {},
            "relation_update_candidates": proto_self_result.get("relation_update_candidates") or [],
            "trust_commitment_snapshot": proto_self_result.get("trust_commitment_snapshot") or {},
            "social_policy_hints": proto_self_result.get("social_policy_hints") or {},
            "repair_proposal_candidates": proto_self_result.get("repair_proposal_candidates") or [],
            "social_writeback_candidate": proto_self_result.get("social_writeback_candidate"),
            "social_context": (proto_self_result.get("trace_payload") or {}).get("social_context") or {},
            "social_writeback": social_writeback,
            "embodied_self_delta": proto_self_result.get("embodied_self_delta") or {},
            "consequence_update_candidates": proto_self_result.get("consequence_update_candidates") or [],
            "resource_boundary_snapshot": proto_self_result.get("resource_boundary_snapshot") or {},
            "embodied_policy_hints": proto_self_result.get("embodied_policy_hints") or {},
            "repair_or_stabilize_proposal_candidates": (
                proto_self_result.get("repair_or_stabilize_proposal_candidates") or []
            ),
            "embodied_writeback_candidate": proto_self_result.get("embodied_writeback_candidate"),
            "environment_context": (proto_self_result.get("trace_payload") or {}).get("environment_context") or {},
            "embodied_writeback": embodied_writeback,
            "self_integration_delta": proto_self_result.get("self_integration_delta") or {},
            "cross_axis_priority_snapshot": proto_self_result.get("cross_axis_priority_snapshot") or {},
            "proposal_conflict_snapshot": proto_self_result.get("proposal_conflict_snapshot") or {},
            "integrated_policy_hints": proto_self_result.get("integrated_policy_hints") or {},
            "integrated_tendency_proposal": proto_self_result.get("integrated_tendency_proposal"),
            "axis_arbitration_hints": proto_self_result.get("axis_arbitration_hints") or {},
            "integration_audit_entries": proto_self_result.get("integration_audit_entries") or [],
            "self_integration_writeback_candidate": proto_self_result.get("self_integration_writeback_candidate"),
            "selfhood_integration_context": (
                proto_self_result.get("trace_payload") or {}
            ).get("selfhood_integration_context")
            or proto_self_result.get("selfhood_integration_context")
            or {},
            "selfhood_integration_writeback": selfhood_integration_writeback,
            "initiative_self_delta": proto_self_result.get("initiative_self_delta") or {},
            "initiative_proposal_candidates": proto_self_result.get("initiative_proposal_candidates") or [],
            "commitment_execution_snapshot": proto_self_result.get("commitment_execution_snapshot") or {},
            "initiative_policy_hints": proto_self_result.get("initiative_policy_hints") or {},
            "host_proactive_candidate": proto_self_result.get("host_proactive_candidate"),
            "initiative_audit_entries": proto_self_result.get("initiative_audit_entries") or [],
            "initiative_writeback_candidate": proto_self_result.get("initiative_writeback_candidate"),
            "initiative_context": (proto_self_result.get("trace_payload") or {}).get("initiative_context") or {},
            "initiative_writeback": initiative_writeback,
            "initiative_realization_delta": proto_self_result.get("initiative_realization_delta") or {},
            "commitment_fulfillment_candidates": (
                proto_self_result.get("commitment_fulfillment_candidates") or []
            ),
            "delivery_readiness_snapshot": proto_self_result.get("delivery_readiness_snapshot") or {},
            "host_lane_hints": proto_self_result.get("host_lane_hints") or [],
            "controlled_delivery_candidate": proto_self_result.get("controlled_delivery_candidate"),
            "initiative_realization_audit_entries": (
                proto_self_result.get("initiative_realization_audit_entries") or []
            ),
            "initiative_realization_writeback_candidate": (
                proto_self_result.get("initiative_realization_writeback_candidate")
            ),
            "initiative_realization_context": (
                (proto_self_result.get("trace_payload") or {}).get("initiative_realization_context")
                or proto_self_result.get("initiative_realization_context")
                or {}
            ),
            "host_proactive_context": (
                (proto_self_result.get("trace_payload") or {}).get("host_proactive_context") or {}
            ),
            "initiative_realization_writeback": initiative_realization_writeback,
        }
        if shadow_h1 is not None:
            state.proto_self_context["shadow_h1"] = shadow_h1
        state.record(
            "proto_self",
            {
                "subject_profile": proto_self_result.get("subject_profile"),
                "policy_hint": proto_self_result.get("policy_hint"),
                "candidate_actions": proto_self_result.get("candidate_actions") or [],
                "self_model_writeback": writeback,
                "endogenous_drive_writeback": endogenous_drive_writeback,
                "reflective_self_writeback": reflective_self_writeback,
                "developmental_writeback": developmental_writeback,
                "social_writeback": social_writeback,
                "embodied_writeback": embodied_writeback,
                "selfhood_integration_writeback": selfhood_integration_writeback,
                "initiative_writeback": initiative_writeback,
                "reflection_writeback_candidate_present": bool(proto_self_result.get("reflection_writeback_candidate")),
                "developmental_writeback_candidate_present": bool(
                    proto_self_result.get("developmental_writeback_candidate")
                ),
                "social_writeback_candidate_present": bool(proto_self_result.get("social_writeback_candidate")),
                "embodied_writeback_candidate_present": bool(proto_self_result.get("embodied_writeback_candidate")),
                "self_integration_writeback_candidate_present": bool(
                    proto_self_result.get("self_integration_writeback_candidate")
                ),
                "initiative_writeback_candidate_present": bool(
                    proto_self_result.get("initiative_writeback_candidate")
                ),
                "initiative_realization_writeback_candidate_present": bool(
                    proto_self_result.get("initiative_realization_writeback_candidate")
                ),
                "reflection_trigger": (
                    proto_self_result.get("reflection_note", {}).get("trigger")
                    if proto_self_result.get("reflection_note")
                    else None
                ),
            },
        )

    def process_external_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        step: int,
        state: RuntimeV2State,
        evidence_collector: Optional[Any] = None,
    ) -> None:
        if not state.last_tool_result:
            return
        external_result_event = build_external_result_event(
            session_id=session_id,
            turn_id=turn_id,
            step=step,
            tool_result=state.last_tool_result,
            state=state,
            self_model_store=self.self_model_store,
            endogenous_drive_store=self.endogenous_drive_store,
            reflective_self_store=self.reflective_self_store,
            developmental_self_store=self.developmental_self_store,
            social_self_store=self.social_self_store,
            embodied_self_store=self.embodied_self_store,
            selfhood_integration_store=self.selfhood_integration_store,
            initiative_self_store=self.initiative_self_store,
            initiative_realization_store=self.initiative_realization_store,
        )
        external_result = normalize_chat_subject_surface(self.adapter.handle_event(external_result_event))
        writeback = self._apply_self_model_writeback(proto_self_result=external_result, state=state)
        endogenous_drive_writeback = self._apply_endogenous_drive_writeback(
            proto_self_result=external_result,
            state=state,
        )
        reflective_self_writeback = self._apply_reflective_self_writeback(
            proto_self_result=external_result,
            state=state,
        )
        developmental_writeback = self._apply_developmental_self_writeback(
            proto_self_result=external_result,
            state=state,
        )
        social_writeback = self._apply_social_self_writeback(
            proto_self_result=external_result,
            state=state,
        )
        embodied_writeback = self._apply_embodied_self_writeback(
            proto_self_result=external_result,
            state=state,
        )
        selfhood_integration_writeback = self._apply_selfhood_integration_writeback(
            proto_self_result=external_result,
            state=state,
        )
        initiative_writeback = self._apply_initiative_self_writeback(
            proto_self_result=external_result,
            state=state,
        )
        collector = self._resolve_collector(evidence_collector)
        if collector is not None:
            collector.capture_openemotion_result(external_result)
        self._capture_trace_in_ledger_or_bridge(
            proto_self_result=external_result,
            collector=collector,
            bridge_stage="external_result_kernel_trace",
        )
        if state.proto_self_context is None:
            state.proto_self_context = {}
        state.proto_self_context["external_result"] = external_result
        state.proto_self_context["self_model_delta"] = external_result.get("self_model_delta") or {}
        state.proto_self_context["self_model_writeback"] = writeback
        state.proto_self_context["endogenous_drive_delta"] = external_result.get("endogenous_drive_delta") or {}
        state.proto_self_context["endogenous_drive_writeback"] = endogenous_drive_writeback
        initiative_realization_writeback = self._apply_initiative_realization_writeback(
            proto_self_result=external_result,
            state=state,
        )
        state.proto_self_context["drive_state_snapshot"] = external_result.get("drive_state_snapshot") or {}
        state.proto_self_context["priority_snapshot"] = external_result.get("priority_snapshot") or {}
        state.proto_self_context["candidate_bias_terms"] = external_result.get("candidate_bias_terms") or {}
        state.proto_self_context["self_maintenance_candidate"] = external_result.get("self_maintenance_candidate")
        state.proto_self_context["reflective_self_delta"] = external_result.get("reflective_self_delta") or {}
        state.proto_self_context["revision_proposal_candidates"] = external_result.get("revision_proposal_candidates") or []
        state.proto_self_context["confidence_adjustment_hints"] = external_result.get("confidence_adjustment_hints") or {}
        state.proto_self_context["maintenance_priority_hints"] = external_result.get("maintenance_priority_hints") or {}
        state.proto_self_context["reflection_writeback_candidate"] = external_result.get("reflection_writeback_candidate")
        state.proto_self_context["reflective_self_writeback"] = reflective_self_writeback
        state.proto_self_context["developmental_self_delta"] = external_result.get("developmental_self_delta") or {}
        state.proto_self_context["developmental_proposal_candidates"] = (
            external_result.get("developmental_proposal_candidates") or []
        )
        state.proto_self_context["developmental_continuity_snapshot"] = (
            external_result.get("developmental_continuity_snapshot") or {}
        )
        state.proto_self_context["developmental_priority_hints"] = (
            external_result.get("developmental_priority_hints") or {}
        )
        state.proto_self_context["developmental_audit_entries"] = (
            external_result.get("developmental_audit_entries") or []
        )
        state.proto_self_context["developmental_writeback_candidate"] = (
            external_result.get("developmental_writeback_candidate")
        )
        state.proto_self_context["developmental_writeback"] = developmental_writeback
        state.proto_self_context["social_self_delta"] = external_result.get("social_self_delta") or {}
        state.proto_self_context["relation_update_candidates"] = external_result.get("relation_update_candidates") or []
        state.proto_self_context["trust_commitment_snapshot"] = (
            external_result.get("trust_commitment_snapshot") or {}
        )
        state.proto_self_context["social_policy_hints"] = external_result.get("social_policy_hints") or {}
        state.proto_self_context["repair_proposal_candidates"] = (
            external_result.get("repair_proposal_candidates") or []
        )
        state.proto_self_context["social_writeback_candidate"] = external_result.get("social_writeback_candidate")
        state.proto_self_context["social_context"] = (external_result.get("trace_payload") or {}).get("social_context") or {}
        state.proto_self_context["social_writeback"] = social_writeback
        state.proto_self_context["embodied_self_delta"] = external_result.get("embodied_self_delta") or {}
        state.proto_self_context["consequence_update_candidates"] = (
            external_result.get("consequence_update_candidates") or []
        )
        state.proto_self_context["resource_boundary_snapshot"] = (
            external_result.get("resource_boundary_snapshot") or {}
        )
        state.proto_self_context["embodied_policy_hints"] = external_result.get("embodied_policy_hints") or {}
        state.proto_self_context["repair_or_stabilize_proposal_candidates"] = (
            external_result.get("repair_or_stabilize_proposal_candidates") or []
        )
        state.proto_self_context["embodied_writeback_candidate"] = external_result.get("embodied_writeback_candidate")
        state.proto_self_context["environment_context"] = (
            external_result.get("trace_payload") or {}
        ).get("environment_context") or {}
        state.proto_self_context["embodied_writeback"] = embodied_writeback
        state.proto_self_context["self_integration_delta"] = external_result.get("self_integration_delta") or {}
        state.proto_self_context["cross_axis_priority_snapshot"] = (
            external_result.get("cross_axis_priority_snapshot") or {}
        )
        state.proto_self_context["proposal_conflict_snapshot"] = (
            external_result.get("proposal_conflict_snapshot") or {}
        )
        state.proto_self_context["integrated_policy_hints"] = external_result.get("integrated_policy_hints") or {}
        state.proto_self_context["integrated_tendency_proposal"] = external_result.get("integrated_tendency_proposal")
        state.proto_self_context["axis_arbitration_hints"] = external_result.get("axis_arbitration_hints") or {}
        state.proto_self_context["integration_audit_entries"] = (
            external_result.get("integration_audit_entries") or []
        )
        state.proto_self_context["self_integration_writeback_candidate"] = (
            external_result.get("self_integration_writeback_candidate")
        )
        state.proto_self_context["selfhood_integration_context"] = (
            external_result.get("trace_payload") or {}
        ).get("selfhood_integration_context") or external_result.get("selfhood_integration_context") or {}
        state.proto_self_context["selfhood_integration_writeback"] = selfhood_integration_writeback
        state.proto_self_context["initiative_self_delta"] = external_result.get("initiative_self_delta") or {}
        state.proto_self_context["initiative_proposal_candidates"] = (
            external_result.get("initiative_proposal_candidates") or []
        )
        state.proto_self_context["commitment_execution_snapshot"] = (
            external_result.get("commitment_execution_snapshot") or {}
        )
        state.proto_self_context["initiative_policy_hints"] = external_result.get("initiative_policy_hints") or {}
        state.proto_self_context["host_proactive_candidate"] = external_result.get("host_proactive_candidate")
        state.proto_self_context["initiative_audit_entries"] = external_result.get("initiative_audit_entries") or []
        state.proto_self_context["initiative_writeback_candidate"] = external_result.get("initiative_writeback_candidate")
        state.proto_self_context["initiative_context"] = (
            external_result.get("trace_payload") or {}
        ).get("initiative_context") or {}
        state.proto_self_context["initiative_writeback"] = initiative_writeback
        state.proto_self_context["initiative_realization_delta"] = (
            external_result.get("initiative_realization_delta") or {}
        )
        state.proto_self_context["commitment_fulfillment_candidates"] = (
            external_result.get("commitment_fulfillment_candidates") or []
        )
        state.proto_self_context["delivery_readiness_snapshot"] = (
            external_result.get("delivery_readiness_snapshot") or {}
        )
        state.proto_self_context["host_lane_hints"] = external_result.get("host_lane_hints") or []
        state.proto_self_context["controlled_delivery_candidate"] = external_result.get(
            "controlled_delivery_candidate"
        )
        state.proto_self_context["initiative_realization_audit_entries"] = (
            external_result.get("initiative_realization_audit_entries") or []
        )
        state.proto_self_context["initiative_realization_writeback_candidate"] = external_result.get(
            "initiative_realization_writeback_candidate"
        )
        state.proto_self_context["initiative_realization_context"] = (
            external_result.get("trace_payload") or {}
        ).get("initiative_realization_context") or external_result.get("initiative_realization_context") or {}
        state.proto_self_context["host_proactive_context"] = (
            external_result.get("trace_payload") or {}
        ).get("host_proactive_context") or {}
        state.proto_self_context["initiative_realization_writeback"] = initiative_realization_writeback
        if external_result.get("candidate_actions") is not None:
            state.proto_self_context["candidate_actions"] = external_result.get("candidate_actions") or []
        if external_result.get("policy_hint"):
            state.proto_self_context["policy_hint"] = external_result.get("policy_hint")
            state.proto_self_context["governor_hint"] = external_result.get("policy_hint", {}).get("governor_hint")
        _update_shadow_h1_proto_self_context(state, external_result, preserve_existing=False)
        if external_result.get("reflection_note"):
            state.record(
                "proto_self_reflection",
                {
                    "trigger": external_result.get("reflection_note", {}).get("trigger"),
                    "diagnosis": external_result.get("reflection_note", {}).get("diagnosis"),
                },
            )

    def process_finalized_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        result: Any,
        state: RuntimeV2State,
        evidence_collector: Optional[Any] = None,
    ) -> None:
        finalized_event = build_finalized_result_event(
            session_id=session_id,
            turn_id=turn_id,
            result=result,
            state=state,
            self_model_store=self.self_model_store,
            endogenous_drive_store=self.endogenous_drive_store,
            reflective_self_store=self.reflective_self_store,
            developmental_self_store=self.developmental_self_store,
            social_self_store=self.social_self_store,
            embodied_self_store=self.embodied_self_store,
            selfhood_integration_store=self.selfhood_integration_store,
            initiative_self_store=self.initiative_self_store,
            initiative_realization_store=self.initiative_realization_store,
        )
        if not finalized_event:
            return
        finalized_result = normalize_chat_subject_surface(self.adapter.handle_event(finalized_event))
        writeback = self._apply_self_model_writeback(proto_self_result=finalized_result, state=state)
        endogenous_drive_writeback = self._apply_endogenous_drive_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        reflective_self_writeback = self._apply_reflective_self_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        developmental_writeback = self._apply_developmental_self_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        social_writeback = self._apply_social_self_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        embodied_writeback = self._apply_embodied_self_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        selfhood_integration_writeback = self._apply_selfhood_integration_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        initiative_writeback = self._apply_initiative_self_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        collector = self._resolve_collector(evidence_collector)
        if collector is not None:
            collector.capture_openemotion_result(finalized_result)
        self._capture_trace_in_ledger_or_bridge(
            proto_self_result=finalized_result,
            collector=collector,
            bridge_stage="finalized_result_kernel_trace",
        )
        if state.proto_self_context is None:
            state.proto_self_context = {}
        state.proto_self_context["finalized_result"] = finalized_result
        state.proto_self_context["last_exec_result"] = finalized_result.get("trace_payload", {}).get("exec_result")
        state.proto_self_context["self_model_delta"] = finalized_result.get("self_model_delta") or {}
        state.proto_self_context["self_model_writeback"] = writeback
        state.proto_self_context["endogenous_drive_delta"] = finalized_result.get("endogenous_drive_delta") or {}
        initiative_realization_writeback = self._apply_initiative_realization_writeback(
            proto_self_result=finalized_result,
            state=state,
        )
        state.proto_self_context["endogenous_drive_writeback"] = endogenous_drive_writeback
        state.proto_self_context["drive_state_snapshot"] = finalized_result.get("drive_state_snapshot") or {}
        state.proto_self_context["priority_snapshot"] = finalized_result.get("priority_snapshot") or {}
        state.proto_self_context["candidate_bias_terms"] = finalized_result.get("candidate_bias_terms") or {}
        state.proto_self_context["self_maintenance_candidate"] = finalized_result.get("self_maintenance_candidate")
        state.proto_self_context["reflective_self_delta"] = finalized_result.get("reflective_self_delta") or {}
        state.proto_self_context["revision_proposal_candidates"] = finalized_result.get("revision_proposal_candidates") or []
        state.proto_self_context["confidence_adjustment_hints"] = finalized_result.get("confidence_adjustment_hints") or {}
        state.proto_self_context["maintenance_priority_hints"] = finalized_result.get("maintenance_priority_hints") or {}
        state.proto_self_context["reflection_writeback_candidate"] = finalized_result.get("reflection_writeback_candidate")
        state.proto_self_context["reflective_self_writeback"] = reflective_self_writeback
        state.proto_self_context["developmental_self_delta"] = finalized_result.get("developmental_self_delta") or {}
        state.proto_self_context["developmental_proposal_candidates"] = (
            finalized_result.get("developmental_proposal_candidates") or []
        )
        state.proto_self_context["developmental_continuity_snapshot"] = (
            finalized_result.get("developmental_continuity_snapshot") or {}
        )
        state.proto_self_context["developmental_priority_hints"] = (
            finalized_result.get("developmental_priority_hints") or {}
        )
        state.proto_self_context["developmental_audit_entries"] = (
            finalized_result.get("developmental_audit_entries") or []
        )
        state.proto_self_context["developmental_writeback_candidate"] = (
            finalized_result.get("developmental_writeback_candidate")
        )
        state.proto_self_context["developmental_writeback"] = developmental_writeback
        state.proto_self_context["social_self_delta"] = finalized_result.get("social_self_delta") or {}
        state.proto_self_context["relation_update_candidates"] = finalized_result.get("relation_update_candidates") or []
        state.proto_self_context["trust_commitment_snapshot"] = (
            finalized_result.get("trust_commitment_snapshot") or {}
        )
        state.proto_self_context["social_policy_hints"] = finalized_result.get("social_policy_hints") or {}
        state.proto_self_context["repair_proposal_candidates"] = (
            finalized_result.get("repair_proposal_candidates") or []
        )
        state.proto_self_context["social_writeback_candidate"] = finalized_result.get("social_writeback_candidate")
        state.proto_self_context["social_context"] = (finalized_result.get("trace_payload") or {}).get("social_context") or {}
        state.proto_self_context["social_writeback"] = social_writeback
        state.proto_self_context["embodied_self_delta"] = finalized_result.get("embodied_self_delta") or {}
        state.proto_self_context["consequence_update_candidates"] = (
            finalized_result.get("consequence_update_candidates") or []
        )
        state.proto_self_context["resource_boundary_snapshot"] = (
            finalized_result.get("resource_boundary_snapshot") or {}
        )
        state.proto_self_context["embodied_policy_hints"] = finalized_result.get("embodied_policy_hints") or {}
        state.proto_self_context["repair_or_stabilize_proposal_candidates"] = (
            finalized_result.get("repair_or_stabilize_proposal_candidates") or []
        )
        state.proto_self_context["embodied_writeback_candidate"] = finalized_result.get("embodied_writeback_candidate")
        state.proto_self_context["environment_context"] = (
            finalized_result.get("trace_payload") or {}
        ).get("environment_context") or {}
        state.proto_self_context["embodied_writeback"] = embodied_writeback
        state.proto_self_context["self_integration_delta"] = finalized_result.get("self_integration_delta") or {}
        state.proto_self_context["cross_axis_priority_snapshot"] = (
            finalized_result.get("cross_axis_priority_snapshot") or {}
        )
        state.proto_self_context["proposal_conflict_snapshot"] = (
            finalized_result.get("proposal_conflict_snapshot") or {}
        )
        state.proto_self_context["integrated_policy_hints"] = finalized_result.get("integrated_policy_hints") or {}
        state.proto_self_context["integrated_tendency_proposal"] = finalized_result.get("integrated_tendency_proposal")
        state.proto_self_context["axis_arbitration_hints"] = finalized_result.get("axis_arbitration_hints") or {}
        state.proto_self_context["integration_audit_entries"] = (
            finalized_result.get("integration_audit_entries") or []
        )
        state.proto_self_context["self_integration_writeback_candidate"] = (
            finalized_result.get("self_integration_writeback_candidate")
        )
        state.proto_self_context["selfhood_integration_context"] = (
            finalized_result.get("trace_payload") or {}
        ).get("selfhood_integration_context") or finalized_result.get("selfhood_integration_context") or {}
        state.proto_self_context["selfhood_integration_writeback"] = selfhood_integration_writeback
        state.proto_self_context["initiative_self_delta"] = finalized_result.get("initiative_self_delta") or {}
        state.proto_self_context["initiative_proposal_candidates"] = (
            finalized_result.get("initiative_proposal_candidates") or []
        )
        state.proto_self_context["commitment_execution_snapshot"] = (
            finalized_result.get("commitment_execution_snapshot") or {}
        )
        state.proto_self_context["initiative_policy_hints"] = finalized_result.get("initiative_policy_hints") or {}
        state.proto_self_context["host_proactive_candidate"] = finalized_result.get("host_proactive_candidate")
        state.proto_self_context["initiative_audit_entries"] = finalized_result.get("initiative_audit_entries") or []
        state.proto_self_context["initiative_writeback_candidate"] = finalized_result.get("initiative_writeback_candidate")
        state.proto_self_context["initiative_context"] = (
            finalized_result.get("trace_payload") or {}
        ).get("initiative_context") or {}
        state.proto_self_context["initiative_writeback"] = initiative_writeback
        state.proto_self_context["initiative_realization_delta"] = (
            finalized_result.get("initiative_realization_delta") or {}
        )
        state.proto_self_context["commitment_fulfillment_candidates"] = (
            finalized_result.get("commitment_fulfillment_candidates") or []
        )
        state.proto_self_context["delivery_readiness_snapshot"] = (
            finalized_result.get("delivery_readiness_snapshot") or {}
        )
        state.proto_self_context["host_lane_hints"] = finalized_result.get("host_lane_hints") or []
        state.proto_self_context["controlled_delivery_candidate"] = finalized_result.get(
            "controlled_delivery_candidate"
        )
        state.proto_self_context["initiative_realization_audit_entries"] = (
            finalized_result.get("initiative_realization_audit_entries") or []
        )
        state.proto_self_context["initiative_realization_writeback_candidate"] = finalized_result.get(
            "initiative_realization_writeback_candidate"
        )
        state.proto_self_context["initiative_realization_context"] = (
            (finalized_result.get("trace_payload") or {}).get("initiative_realization_context")
            or finalized_result.get("initiative_realization_context")
            or {}
        )
        state.proto_self_context["host_proactive_context"] = (
            (finalized_result.get("trace_payload") or {}).get("host_proactive_context") or {}
        )
        state.proto_self_context["initiative_realization_writeback"] = initiative_realization_writeback
        if finalized_result.get("subject_profile"):
            state.proto_self_context["subject_profile"] = finalized_result.get("subject_profile")
        if finalized_result.get("policy_hint"):
            state.proto_self_context["policy_hint"] = finalized_result.get("policy_hint")
            state.proto_self_context["governor_hint"] = finalized_result.get("policy_hint", {}).get("governor_hint")
        _update_shadow_h1_proto_self_context(state, finalized_result, preserve_existing=True)

    def process_idle_check(
        self,
        *,
        session_id: str,
        turn_id: str,
        state: RuntimeV2State,
        evidence_collector: Optional[Any] = None,
    ) -> None:
        idle_event = build_idle_check_event(
            session_id=session_id,
            turn_id=turn_id,
            state=state,
            self_model_store=self.self_model_store,
            endogenous_drive_store=self.endogenous_drive_store,
            reflective_self_store=self.reflective_self_store,
            developmental_self_store=self.developmental_self_store,
            social_self_store=self.social_self_store,
            embodied_self_store=self.embodied_self_store,
            selfhood_integration_store=self.selfhood_integration_store,
            initiative_self_store=self.initiative_self_store,
            initiative_realization_store=self.initiative_realization_store,
        )
        if not idle_event:
            return
        idle_result = normalize_chat_subject_surface(self.adapter.handle_event(idle_event))
        writeback = self._apply_self_model_writeback(proto_self_result=idle_result, state=state)
        endogenous_drive_writeback = self._apply_endogenous_drive_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        reflective_self_writeback = self._apply_reflective_self_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        developmental_writeback = self._apply_developmental_self_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        social_writeback = self._apply_social_self_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        embodied_writeback = self._apply_embodied_self_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        selfhood_integration_writeback = self._apply_selfhood_integration_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        initiative_writeback = self._apply_initiative_self_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        collector = self._resolve_collector(evidence_collector)
        if collector is not None:
            collector.capture_openemotion_result(idle_result)
        self._capture_trace_in_ledger_or_bridge(
            proto_self_result=idle_result,
            collector=collector,
            bridge_stage="idle_check_kernel_trace",
        )
        if state.proto_self_context is None:
            state.proto_self_context = {}
        state.proto_self_context["idle_check"] = idle_result
        state.proto_self_context["subject_profile"] = idle_result.get("subject_profile")
        state.proto_self_context["candidate_actions"] = idle_result.get("candidate_actions") or []
        state.proto_self_context["self_model_delta"] = idle_result.get("self_model_delta") or {}
        state.proto_self_context["self_model_writeback"] = writeback
        initiative_realization_writeback = self._apply_initiative_realization_writeback(
            proto_self_result=idle_result,
            state=state,
        )
        state.proto_self_context["endogenous_drive_delta"] = idle_result.get("endogenous_drive_delta") or {}
        state.proto_self_context["endogenous_drive_writeback"] = endogenous_drive_writeback
        state.proto_self_context["drive_state_snapshot"] = idle_result.get("drive_state_snapshot") or {}
        state.proto_self_context["priority_snapshot"] = idle_result.get("priority_snapshot") or {}
        state.proto_self_context["candidate_bias_terms"] = idle_result.get("candidate_bias_terms") or {}
        state.proto_self_context["self_maintenance_candidate"] = idle_result.get("self_maintenance_candidate")
        state.proto_self_context["reflective_self_delta"] = idle_result.get("reflective_self_delta") or {}
        state.proto_self_context["revision_proposal_candidates"] = idle_result.get("revision_proposal_candidates") or []
        state.proto_self_context["confidence_adjustment_hints"] = idle_result.get("confidence_adjustment_hints") or {}
        state.proto_self_context["maintenance_priority_hints"] = idle_result.get("maintenance_priority_hints") or {}
        state.proto_self_context["reflection_writeback_candidate"] = idle_result.get("reflection_writeback_candidate")
        state.proto_self_context["reflective_self_writeback"] = reflective_self_writeback
        state.proto_self_context["developmental_self_delta"] = idle_result.get("developmental_self_delta") or {}
        state.proto_self_context["developmental_proposal_candidates"] = (
            idle_result.get("developmental_proposal_candidates") or []
        )
        state.proto_self_context["developmental_continuity_snapshot"] = (
            idle_result.get("developmental_continuity_snapshot") or {}
        )
        state.proto_self_context["developmental_priority_hints"] = (
            idle_result.get("developmental_priority_hints") or {}
        )
        state.proto_self_context["developmental_audit_entries"] = (
            idle_result.get("developmental_audit_entries") or []
        )
        state.proto_self_context["developmental_writeback_candidate"] = (
            idle_result.get("developmental_writeback_candidate")
        )
        state.proto_self_context["developmental_writeback"] = developmental_writeback
        state.proto_self_context["social_self_delta"] = idle_result.get("social_self_delta") or {}
        state.proto_self_context["relation_update_candidates"] = idle_result.get("relation_update_candidates") or []
        state.proto_self_context["trust_commitment_snapshot"] = idle_result.get("trust_commitment_snapshot") or {}
        state.proto_self_context["social_policy_hints"] = idle_result.get("social_policy_hints") or {}
        state.proto_self_context["repair_proposal_candidates"] = idle_result.get("repair_proposal_candidates") or []
        state.proto_self_context["social_writeback_candidate"] = idle_result.get("social_writeback_candidate")
        state.proto_self_context["social_context"] = (idle_result.get("trace_payload") or {}).get("social_context") or {}
        state.proto_self_context["social_writeback"] = social_writeback
        state.proto_self_context["embodied_self_delta"] = idle_result.get("embodied_self_delta") or {}
        state.proto_self_context["consequence_update_candidates"] = idle_result.get("consequence_update_candidates") or []
        state.proto_self_context["resource_boundary_snapshot"] = idle_result.get("resource_boundary_snapshot") or {}
        state.proto_self_context["embodied_policy_hints"] = idle_result.get("embodied_policy_hints") or {}
        state.proto_self_context["repair_or_stabilize_proposal_candidates"] = (
            idle_result.get("repair_or_stabilize_proposal_candidates") or []
        )
        state.proto_self_context["embodied_writeback_candidate"] = idle_result.get("embodied_writeback_candidate")
        state.proto_self_context["environment_context"] = (
            idle_result.get("trace_payload") or {}
        ).get("environment_context") or {}
        state.proto_self_context["embodied_writeback"] = embodied_writeback
        state.proto_self_context["self_integration_delta"] = idle_result.get("self_integration_delta") or {}
        state.proto_self_context["cross_axis_priority_snapshot"] = (
            idle_result.get("cross_axis_priority_snapshot") or {}
        )
        state.proto_self_context["proposal_conflict_snapshot"] = (
            idle_result.get("proposal_conflict_snapshot") or {}
        )
        state.proto_self_context["integrated_policy_hints"] = idle_result.get("integrated_policy_hints") or {}
        state.proto_self_context["integrated_tendency_proposal"] = idle_result.get("integrated_tendency_proposal")
        state.proto_self_context["axis_arbitration_hints"] = idle_result.get("axis_arbitration_hints") or {}
        state.proto_self_context["integration_audit_entries"] = idle_result.get("integration_audit_entries") or []
        state.proto_self_context["self_integration_writeback_candidate"] = (
            idle_result.get("self_integration_writeback_candidate")
        )
        state.proto_self_context["selfhood_integration_context"] = (
            idle_result.get("trace_payload") or {}
        ).get("selfhood_integration_context") or idle_result.get("selfhood_integration_context") or {}
        state.proto_self_context["selfhood_integration_writeback"] = selfhood_integration_writeback
        state.proto_self_context["initiative_self_delta"] = idle_result.get("initiative_self_delta") or {}
        state.proto_self_context["initiative_proposal_candidates"] = (
            idle_result.get("initiative_proposal_candidates") or []
        )
        state.proto_self_context["commitment_execution_snapshot"] = (
            idle_result.get("commitment_execution_snapshot") or {}
        )
        state.proto_self_context["initiative_policy_hints"] = idle_result.get("initiative_policy_hints") or {}
        state.proto_self_context["host_proactive_candidate"] = idle_result.get("host_proactive_candidate")
        state.proto_self_context["initiative_audit_entries"] = idle_result.get("initiative_audit_entries") or []
        state.proto_self_context["initiative_writeback_candidate"] = idle_result.get("initiative_writeback_candidate")
        state.proto_self_context["initiative_context"] = (
            idle_result.get("trace_payload") or {}
        ).get("initiative_context") or {}
        state.proto_self_context["initiative_writeback"] = initiative_writeback
        state.proto_self_context["initiative_realization_delta"] = (
            idle_result.get("initiative_realization_delta") or {}
        )
        state.proto_self_context["commitment_fulfillment_candidates"] = (
            idle_result.get("commitment_fulfillment_candidates") or []
        )
        state.proto_self_context["delivery_readiness_snapshot"] = (
            idle_result.get("delivery_readiness_snapshot") or {}
        )
        state.proto_self_context["host_lane_hints"] = idle_result.get("host_lane_hints") or []
        state.proto_self_context["controlled_delivery_candidate"] = idle_result.get(
            "controlled_delivery_candidate"
        )
        state.proto_self_context["initiative_realization_audit_entries"] = (
            idle_result.get("initiative_realization_audit_entries") or []
        )
        state.proto_self_context["initiative_realization_writeback_candidate"] = idle_result.get(
            "initiative_realization_writeback_candidate"
        )
        state.proto_self_context["initiative_realization_context"] = (
            (idle_result.get("trace_payload") or {}).get("initiative_realization_context")
            or idle_result.get("initiative_realization_context")
            or {}
        )
        state.proto_self_context["host_proactive_context"] = (
            (idle_result.get("trace_payload") or {}).get("host_proactive_context") or {}
        )
        state.proto_self_context["initiative_realization_writeback"] = initiative_realization_writeback
        if idle_result.get("policy_hint"):
            state.proto_self_context["policy_hint"] = idle_result.get("policy_hint")
            state.proto_self_context["governor_hint"] = idle_result.get("policy_hint", {}).get("governor_hint")
        _update_shadow_h1_proto_self_context(state, idle_result, preserve_existing=False)

    def process_developmental_tick(
        self,
        *,
        session_id: str,
        turn_id: str,
        state: RuntimeV2State,
        observation_source: str = "synthetic",
        trigger: str = "idle",
        idle_seconds: float = 0.0,
        unresolved_tensions: Optional[list] = None,
        long_term_goals: Optional[list] = None,
        observation_refs: Optional[list] = None,
        state_snapshot: Optional[Dict[str, Any]] = None,
        replay_seed: Optional[int] = None,
        evidence_collector: Optional[Any] = None,
        force_enable: bool = False,
    ) -> Optional[Dict[str, Any]]:
        developmental_event = build_developmental_tick_event(
            session_id=session_id,
            turn_id=turn_id,
            state=state,
            observation_source=observation_source,
            trigger=trigger,
            idle_seconds=idle_seconds,
            unresolved_tensions=unresolved_tensions,
            long_term_goals=long_term_goals,
            observation_refs=observation_refs,
            state_snapshot=state_snapshot,
            replay_seed=replay_seed,
            force_enable=force_enable,
            self_model_store=self.self_model_store,
            endogenous_drive_store=self.endogenous_drive_store,
            reflective_self_store=self.reflective_self_store,
            developmental_self_store=self.developmental_self_store,
            social_self_store=self.social_self_store,
            embodied_self_store=self.embodied_self_store,
            selfhood_integration_store=self.selfhood_integration_store,
            initiative_self_store=self.initiative_self_store,
            initiative_realization_store=self.initiative_realization_store,
        )
        if not developmental_event:
            return None
        developmental_result = normalize_chat_subject_surface(self.adapter.handle_event(developmental_event))
        writeback = self._apply_self_model_writeback(proto_self_result=developmental_result, state=state)
        endogenous_drive_writeback = self._apply_endogenous_drive_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        reflective_self_writeback = self._apply_reflective_self_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        developmental_writeback = self._apply_developmental_self_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        social_writeback = self._apply_social_self_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        embodied_writeback = self._apply_embodied_self_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        selfhood_integration_writeback = self._apply_selfhood_integration_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        initiative_writeback = self._apply_initiative_self_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        collector = self._resolve_collector(evidence_collector)
        if collector is not None:
            collector.capture_normalized_event(developmental_event)
            collector.capture_openemotion_result(developmental_result)
        self._capture_trace_in_ledger_or_bridge(
            proto_self_result=developmental_result,
            collector=collector,
            bridge_stage="developmental_tick_kernel_trace",
        )
        if state.proto_self_context is None:
            state.proto_self_context = {}
        developmental_summary = dict(developmental_result.get("developmental_summary") or {})
        state.proto_self_context["developmental_summary"] = developmental_summary
        state.proto_self_context["shadow_revision"] = developmental_summary.get("shadow_revision")
        state.proto_self_context["last_developmental_cycle"] = developmental_summary.get("cycle_id")
        initiative_realization_writeback = self._apply_initiative_realization_writeback(
            proto_self_result=developmental_result,
            state=state,
        )
        state.proto_self_context["self_model_delta"] = developmental_result.get("self_model_delta") or {}
        state.proto_self_context["self_model_writeback"] = writeback
        state.proto_self_context["endogenous_drive_delta"] = developmental_result.get("endogenous_drive_delta") or {}
        state.proto_self_context["endogenous_drive_writeback"] = endogenous_drive_writeback
        state.proto_self_context["drive_state_snapshot"] = developmental_result.get("drive_state_snapshot") or {}
        state.proto_self_context["priority_snapshot"] = developmental_result.get("priority_snapshot") or {}
        state.proto_self_context["candidate_bias_terms"] = developmental_result.get("candidate_bias_terms") or {}
        state.proto_self_context["self_maintenance_candidate"] = developmental_result.get("self_maintenance_candidate")
        state.proto_self_context["reflective_self_delta"] = developmental_result.get("reflective_self_delta") or {}
        state.proto_self_context["revision_proposal_candidates"] = developmental_result.get("revision_proposal_candidates") or []
        state.proto_self_context["confidence_adjustment_hints"] = developmental_result.get("confidence_adjustment_hints") or {}
        state.proto_self_context["maintenance_priority_hints"] = developmental_result.get("maintenance_priority_hints") or {}
        state.proto_self_context["reflection_writeback_candidate"] = developmental_result.get("reflection_writeback_candidate")
        state.proto_self_context["reflective_self_writeback"] = reflective_self_writeback
        state.proto_self_context["developmental_self_delta"] = developmental_result.get("developmental_self_delta") or {}
        state.proto_self_context["developmental_proposal_candidates"] = (
            developmental_result.get("developmental_proposal_candidates") or []
        )
        state.proto_self_context["developmental_continuity_snapshot"] = (
            developmental_result.get("developmental_continuity_snapshot") or {}
        )
        state.proto_self_context["developmental_priority_hints"] = (
            developmental_result.get("developmental_priority_hints") or {}
        )
        state.proto_self_context["developmental_audit_entries"] = (
            developmental_result.get("developmental_audit_entries") or []
        )
        state.proto_self_context["developmental_writeback_candidate"] = (
            developmental_result.get("developmental_writeback_candidate")
        )
        state.proto_self_context["developmental_writeback"] = developmental_writeback
        state.proto_self_context["social_self_delta"] = developmental_result.get("social_self_delta") or {}
        state.proto_self_context["relation_update_candidates"] = (
            developmental_result.get("relation_update_candidates") or []
        )
        state.proto_self_context["trust_commitment_snapshot"] = (
            developmental_result.get("trust_commitment_snapshot") or {}
        )
        state.proto_self_context["social_policy_hints"] = developmental_result.get("social_policy_hints") or {}
        state.proto_self_context["repair_proposal_candidates"] = (
            developmental_result.get("repair_proposal_candidates") or []
        )
        state.proto_self_context["social_writeback_candidate"] = developmental_result.get("social_writeback_candidate")
        state.proto_self_context["social_context"] = (
            developmental_result.get("trace_payload") or {}
        ).get("social_context") or {}
        state.proto_self_context["social_writeback"] = social_writeback
        state.proto_self_context["embodied_self_delta"] = developmental_result.get("embodied_self_delta") or {}
        state.proto_self_context["consequence_update_candidates"] = (
            developmental_result.get("consequence_update_candidates") or []
        )
        state.proto_self_context["resource_boundary_snapshot"] = (
            developmental_result.get("resource_boundary_snapshot") or {}
        )
        state.proto_self_context["embodied_policy_hints"] = developmental_result.get("embodied_policy_hints") or {}
        state.proto_self_context["repair_or_stabilize_proposal_candidates"] = (
            developmental_result.get("repair_or_stabilize_proposal_candidates") or []
        )
        state.proto_self_context["embodied_writeback_candidate"] = developmental_result.get("embodied_writeback_candidate")
        state.proto_self_context["environment_context"] = (
            developmental_result.get("trace_payload") or {}
        ).get("environment_context") or {}
        state.proto_self_context["embodied_writeback"] = embodied_writeback
        state.proto_self_context["self_integration_delta"] = developmental_result.get("self_integration_delta") or {}
        state.proto_self_context["cross_axis_priority_snapshot"] = (
            developmental_result.get("cross_axis_priority_snapshot") or {}
        )
        state.proto_self_context["proposal_conflict_snapshot"] = (
            developmental_result.get("proposal_conflict_snapshot") or {}
        )
        state.proto_self_context["integrated_policy_hints"] = (
            developmental_result.get("integrated_policy_hints") or {}
        )
        state.proto_self_context["integrated_tendency_proposal"] = (
            developmental_result.get("integrated_tendency_proposal")
        )
        state.proto_self_context["axis_arbitration_hints"] = developmental_result.get("axis_arbitration_hints") or {}
        state.proto_self_context["integration_audit_entries"] = (
            developmental_result.get("integration_audit_entries") or []
        )
        state.proto_self_context["self_integration_writeback_candidate"] = (
            developmental_result.get("self_integration_writeback_candidate")
        )
        state.proto_self_context["selfhood_integration_context"] = (
            developmental_result.get("trace_payload") or {}
        ).get("selfhood_integration_context") or developmental_result.get("selfhood_integration_context") or {}
        state.proto_self_context["selfhood_integration_writeback"] = selfhood_integration_writeback
        state.proto_self_context["initiative_self_delta"] = developmental_result.get("initiative_self_delta") or {}
        state.proto_self_context["initiative_proposal_candidates"] = (
            developmental_result.get("initiative_proposal_candidates") or []
        )
        state.proto_self_context["commitment_execution_snapshot"] = (
            developmental_result.get("commitment_execution_snapshot") or {}
        )
        state.proto_self_context["initiative_policy_hints"] = developmental_result.get("initiative_policy_hints") or {}
        state.proto_self_context["host_proactive_candidate"] = developmental_result.get("host_proactive_candidate")
        state.proto_self_context["initiative_audit_entries"] = (
            developmental_result.get("initiative_audit_entries") or []
        )
        state.proto_self_context["initiative_writeback_candidate"] = (
            developmental_result.get("initiative_writeback_candidate")
        )
        state.proto_self_context["initiative_context"] = (
            developmental_result.get("trace_payload") or {}
        ).get("initiative_context") or {}
        state.proto_self_context["initiative_writeback"] = initiative_writeback
        state.proto_self_context["initiative_realization_delta"] = (
            developmental_result.get("initiative_realization_delta") or {}
        )
        state.proto_self_context["commitment_fulfillment_candidates"] = (
            developmental_result.get("commitment_fulfillment_candidates") or []
        )
        state.proto_self_context["delivery_readiness_snapshot"] = (
            developmental_result.get("delivery_readiness_snapshot") or {}
        )
        state.proto_self_context["host_lane_hints"] = developmental_result.get("host_lane_hints") or []
        state.proto_self_context["controlled_delivery_candidate"] = developmental_result.get(
            "controlled_delivery_candidate"
        )
        state.proto_self_context["initiative_realization_audit_entries"] = (
            developmental_result.get("initiative_realization_audit_entries") or []
        )
        state.proto_self_context["initiative_realization_writeback_candidate"] = developmental_result.get(
            "initiative_realization_writeback_candidate"
        )
        state.proto_self_context["initiative_realization_context"] = (
            (developmental_result.get("trace_payload") or {}).get("initiative_realization_context")
            or developmental_result.get("initiative_realization_context")
            or {}
        )
        state.proto_self_context["host_proactive_context"] = (
            (developmental_result.get("trace_payload") or {}).get("host_proactive_context") or {}
        )
        state.proto_self_context["initiative_realization_writeback"] = initiative_realization_writeback
        state.proto_self_context["background_thought_candidates"] = list(
            developmental_summary.get("background_thought_candidates") or []
        )
        state.record(
            "proto_self_developmental",
            {
                "cycle_id": developmental_summary.get("cycle_id"),
                "trigger": developmental_summary.get("trigger"),
                "gate_status": developmental_summary.get("gate_status"),
                "observation_source": developmental_summary.get("observation_source"),
                "background_thought_candidate_count": developmental_summary.get("background_thought_candidate_count", 0),
                "developmental_writeback_gate_verdict": (
                    developmental_writeback or {}
                ).get("decision", {}).get("gate_verdict"),
                "developmental_proposal_candidate_count": len(
                    developmental_result.get("developmental_proposal_candidates") or []
                ),
                "embodied_writeback_gate_verdict": (embodied_writeback or {}).get("decision", {}).get("gate_verdict"),
                "embodied_proposal_candidate_count": len(
                    developmental_result.get("repair_or_stabilize_proposal_candidates") or []
                ),
                "selfhood_integration_writeback_gate_verdict": (
                    selfhood_integration_writeback or {}
                ).get("decision", {}).get("gate_verdict"),
                "self_integration_writeback_candidate_present": bool(
                    developmental_result.get("self_integration_writeback_candidate")
                ),
                "initiative_writeback_gate_verdict": (
                    initiative_writeback or {}
                ).get("decision", {}).get("gate_verdict"),
                "initiative_writeback_candidate_present": bool(
                    developmental_result.get("initiative_writeback_candidate")
                ),
                "initiative_realization_writeback_gate_verdict": (
                    initiative_realization_writeback or {}
                ).get("decision", {}).get("gate_verdict"),
                "initiative_realization_writeback_candidate_present": bool(
                    developmental_result.get("initiative_realization_writeback_candidate")
                ),
            },
        )
        return developmental_result

    def capture_response_plan(self, *, result: Any, evidence_collector: Optional[Any] = None) -> None:
        collector = self._resolve_collector(evidence_collector)
        if collector is None:
            return
        collector.capture_response_plan(build_response_plan_payload(result=result))
