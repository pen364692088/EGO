from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.subject_system_v1 import normalize_proto_self_result

from .state import RuntimeV2State


SUBJECT_SYSTEM_V1_CONTEXT_KEY = "subject_system_v1"
SUBJECT_SYSTEM_V1_COMPAT_MIRROR_KEYS = {
    "subject_system_identity_invariants",
    "subject_system_trace_payload",
    "memory_update",
    "appraisal_state_delta",
    "reflection_writeback_candidate",
    "host_proactive_candidate",
    "response_tendency",
    "policy_hint",
    "governor_hint",
}


def get_canonical_subject_system_v1_context(state: RuntimeV2State | Any) -> Dict[str, Any]:
    proto_self_context = dict(getattr(state, "proto_self_context", None) or {})
    return dict(proto_self_context.get(SUBJECT_SYSTEM_V1_CONTEXT_KEY) or {})


def write_subject_system_v1_context(
    *,
    state: RuntimeV2State,
    proto_self_result: Dict[str, Any] | None,
    runtime_summary: Dict[str, Any] | None,
) -> Dict[str, Any]:
    normalized = normalize_proto_self_result(
        proto_self_result=proto_self_result,
        runtime_summary=runtime_summary,
    ).to_dict()

    if state.proto_self_context is None:
        state.proto_self_context = {}

    state.proto_self_context[SUBJECT_SYSTEM_V1_CONTEXT_KEY] = normalized
    # Compatibility mirrors for legacy readers only. Current-lane code must read
    # the canonical `subject_system_v1` record above.
    state.proto_self_context["subject_system_identity_invariants"] = dict(
        normalized.get("identity_invariants") or {}
    )
    state.proto_self_context["subject_system_trace_payload"] = dict(normalized.get("trace_payload") or {})
    state.proto_self_context["memory_update"] = dict(normalized.get("memory_update") or {})
    state.proto_self_context["appraisal_state_delta"] = dict(normalized.get("appraisal_state_delta") or {})
    state.proto_self_context["reflection_writeback_candidate"] = normalized.get(
        "reflection_writeback_candidate"
    )
    state.proto_self_context["host_proactive_candidate"] = normalized.get("host_proactive_candidate")
    state.proto_self_context["response_tendency"] = normalized.get("response_tendency")
    state.proto_self_context["policy_hint"] = dict(normalized.get("policy_hint") or {})
    state.proto_self_context["governor_hint"] = (
        dict(normalized.get("policy_hint") or {}).get("governor_hint")
    )
    return normalized


def clear_host_proactive_decision(state: RuntimeV2State) -> None:
    if state.proto_self_context is None:
        return
    state.proto_self_context.pop("host_proactive_decision", None)


def set_host_proactive_decision(
    *,
    state: RuntimeV2State,
    decision: Dict[str, Any] | None,
) -> Optional[Dict[str, Any]]:
    if state.proto_self_context is None:
        state.proto_self_context = {}
    if not decision:
        state.proto_self_context.pop("host_proactive_decision", None)
        return None
    payload = dict(decision)
    state.proto_self_context["host_proactive_decision"] = payload
    return payload
