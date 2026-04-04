from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import logging
import os

from openemotion.proto_self_v2.seed_schemas import SEED_SCHEMA_VERSION, SEED_SUBJECT_PROFILE
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
DEFAULT_SELF_MODEL_IDENTITY_HANDLE = "openemotion"
DEFAULT_ENDOGENOUS_DRIVE_IDENTITY_HANDLE = "openemotion"
DEFAULT_REFLECTIVE_SELF_IDENTITY_HANDLE = "openemotion"
DEFAULT_DEVELOPMENTAL_SELF_IDENTITY_HANDLE = "openemotion"


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


def _seed_runtime_summary(state: RuntimeV2State) -> Dict[str, Any]:
    ingress_context = state.ingress_context or {}
    resolved_target = _resolved_target(state)
    return {
        "runtime": "runtime_v2",
        "state_scope": "agent_global",
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
    snapshot = store.load_snapshot(_resolve_self_model_identity_handle(state))
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


def _inject_developmental_context(
    runtime_summary: Dict[str, Any],
    *,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    runtime_summary["developmental_context"] = _build_developmental_context(state)
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
) -> Dict[str, Any]:
    risk_level = assess_risk_level(user_input)
    restore_observation = (state.ingress_context or {}).get("restore_observation")
    schema_version = resolve_proto_self_schema_version(state)
    if schema_version == "proto_self.v2":
        ingress_context = state.ingress_context or {}
        subject_profile = resolve_proto_self_subject_profile(state)
        runtime_summary = _inject_self_model_context(
            {
                "runtime": "runtime_v2",
                "state_scope": "agent_global",
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
        runtime_summary.update(
            {
                k: v
                for k, v in _seed_runtime_summary(state).items()
                if v is not None
            }
        )
        runtime_summary = _inject_developmental_context(runtime_summary, state=state)
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
            "safety_context": {
                "risk_level": risk_level,
            },
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
                safety_context={"risk_level": risk_level, "blocked": False},
            )
        return payload
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
        "runtime_summary": {
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            "restore_observation": restore_observation,
        },
        "safety_context": {
            "risk_level": risk_level,
        },
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
                    "state_scope": "agent_global",
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
        payload["runtime_summary"] = _inject_developmental_context(
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
        "runtime_summary": {
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
        },
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
                "state_scope": "agent_global",
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
    payload["runtime_summary"] = _inject_developmental_context(
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
                "state_scope": "agent_global",
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
    event["runtime_summary"] = _inject_developmental_context(
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
            "state_scope": "agent_global",
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
    runtime_summary = _inject_developmental_context(
        runtime_summary,
        state=state,
    )
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
    payload = {
        "status": result.status,
        "delivery_kind": result.delivery_kind if result.reply else None,
        "reply_length": len(result.reply_text) if result.reply_text else 0,
    }
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
        )
        proto_self_result = self.adapter.handle_event(proto_self_event)
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
        collector = self._resolve_collector(evidence_collector)
        if collector is not None:
            collector.capture_normalized_event(proto_self_event)
            collector.capture_openemotion_result(proto_self_result)
        self._capture_trace_in_ledger_or_bridge(
            proto_self_result=proto_self_result,
            collector=collector,
            bridge_stage="ingress_kernel_trace",
        )
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
        }
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
                "reflection_writeback_candidate_present": bool(proto_self_result.get("reflection_writeback_candidate")),
                "developmental_writeback_candidate_present": bool(
                    proto_self_result.get("developmental_writeback_candidate")
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
        )
        external_result = self.adapter.handle_event(external_result_event)
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
        if external_result.get("candidate_actions") is not None:
            state.proto_self_context["candidate_actions"] = external_result.get("candidate_actions") or []
        if external_result.get("policy_hint"):
            state.proto_self_context["policy_hint"] = external_result.get("policy_hint")
            state.proto_self_context["governor_hint"] = external_result.get("policy_hint", {}).get("governor_hint")
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
        )
        if not finalized_event:
            return
        finalized_result = self.adapter.handle_event(finalized_event)
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
        if finalized_result.get("policy_hint"):
            state.proto_self_context["policy_hint"] = finalized_result.get("policy_hint")
            state.proto_self_context["governor_hint"] = finalized_result.get("policy_hint", {}).get("governor_hint")

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
        )
        if not idle_event:
            return
        idle_result = self.adapter.handle_event(idle_event)
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
        if idle_result.get("policy_hint"):
            state.proto_self_context["policy_hint"] = idle_result.get("policy_hint")
            state.proto_self_context["governor_hint"] = idle_result.get("policy_hint", {}).get("governor_hint")

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
        )
        if not developmental_event:
            return None
        developmental_result = self.adapter.handle_event(developmental_event)
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
            },
        )
        return developmental_result

    def capture_response_plan(self, *, result: Any, evidence_collector: Optional[Any] = None) -> None:
        collector = self._resolve_collector(evidence_collector)
        if collector is None:
            return
        collector.capture_response_plan(build_response_plan_payload(result=result))
