from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any, Dict, Optional, Sequence

from app.restore_runtime import PendingRestoreObservation
from app.runtime_v2.semantic_parser import build_runtime_status_reply

from .memory_claim_gate import (
    CurrentSessionRecallGrounding,
    MemoryClaimVerdict,
    build_current_session_recall_grounding,
    evaluate_memory_claim,
)


@dataclass(frozen=True)
class ResponsePlan:
    kind: str
    reply_text: str
    delivery_kind: str
    authority_source: str
    reply_authority: str
    chat_cadence_mode: Optional[str] = None
    speaker_mode: str = "reflect"
    epistemic_status: str = "uncertain"
    commitment_level: str = "soft"
    must_include: tuple[str, ...] = ()
    must_not_upgrade: Dict[str, bool] = field(default_factory=dict)
    tone_bounds: Dict[str, Any] = field(default_factory=dict)
    memory_claim_verdict: Optional[MemoryClaimVerdict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _apply_final_text_metadata(metadata: Dict[str, Any], reply_text: str, *, limit: int = 200) -> Dict[str, Any]:
    preview = str(reply_text or "").strip()
    metadata["final_text_length"] = len(preview)
    if not preview:
        return metadata
    metadata["final_text_preview"] = preview[:limit]
    metadata["final_text_hash"] = hashlib.sha256(preview.encode("utf-8")).hexdigest()[:16]
    return metadata


def _build_pending_result_continuation_metadata(state: Any) -> Optional[Dict[str, Any]]:
    if state is None or not hasattr(state, "build_pending_result_continuation_summary"):
        return None
    try:
        summary = state.build_pending_result_continuation_summary()
    except Exception:
        return None
    return dict(summary or {}) if summary else None


def _apply_continuation_metadata(metadata: Dict[str, Any], state: Any) -> Dict[str, Any]:
    ingress_context = dict(getattr(state, "ingress_context", None) or {}) if state is not None else {}
    if "recent_result_binding" not in metadata and "recent_result_binding" in ingress_context:
        metadata["recent_result_binding"] = bool(ingress_context.get("recent_result_binding"))
    if "correction_context" not in metadata and "correction_context" in ingress_context:
        metadata["correction_context"] = bool(ingress_context.get("correction_context"))
    pending_result_continuation = _build_pending_result_continuation_metadata(state)
    if pending_result_continuation and "pending_result_continuation" not in metadata:
        metadata["pending_result_continuation"] = pending_result_continuation
    return metadata


def build_direct_response_plan(
    reply_text: str,
    *,
    kind: str,
    delivery_kind: str,
    authority_source: str,
    reply_authority: str = "model_chat",
    metadata: Optional[Dict[str, Any]] = None,
    memory_claim_verdict: Optional[MemoryClaimVerdict] = None,
    state: Any = None,
    restore_observation: Optional[PendingRestoreObservation] = None,
) -> ResponsePlan:
    metadata_dict = dict(metadata or {})
    conversation_act = str(metadata_dict.get("conversation_act") or _build_conversation_act(state)).strip() or "runtime_result"
    chat_cadence_mode = _resolve_chat_cadence_mode(
        kind=kind,
        delivery_kind=delivery_kind,
        metadata=metadata_dict,
    )
    effective_restore = _resolve_restore_observation(state, restore_observation=restore_observation)
    current_session_grounding = _build_current_session_recall_grounding(state)
    expression_contract = _build_expression_contract(
        state,
        reply_authority=reply_authority,
        conversation_act=conversation_act,
        metadata=metadata_dict,
    )
    gated_reply_text, verdict, final_authority = _apply_memory_claim_contract(
        reply_text,
        kind=kind,
        reply_authority=reply_authority,
        restore_observation=effective_restore,
        current_session_grounding=current_session_grounding,
        explicit_verdict=memory_claim_verdict,
    )
    metadata_dict.setdefault("conversation_act", conversation_act)
    metadata_dict.setdefault("reply_origin", _infer_reply_origin(state, kind, final_authority))
    if chat_cadence_mode:
        metadata_dict.setdefault("chat_cadence_mode", chat_cadence_mode)
    metadata_dict["memory_claim_reason"] = verdict.reason
    metadata_dict["memory_claim_allowed"] = verdict.allowed
    metadata_dict["memory_claim_detected"] = verdict.claim_detected
    metadata_dict["memory_claim_grounding_source"] = (
        current_session_grounding.authority_source if current_session_grounding is not None else None
    )
    _apply_continuation_metadata(metadata_dict, state)
    _apply_final_text_metadata(metadata_dict, gated_reply_text)
    intent_contract_source = _build_intent_contract_source(
        state,
        reply_authority=final_authority,
        conversation_act=conversation_act,
        metadata=metadata_dict,
        restore_observation=effective_restore,
    )
    metadata_dict["intent_contract_source"] = intent_contract_source
    metadata_dict["intent_contract_source_status"] = intent_contract_source.get("source_status")
    return ResponsePlan(
        kind=kind,
        reply_text=gated_reply_text,
        delivery_kind=delivery_kind,
        authority_source=authority_source,
        reply_authority=final_authority,
        chat_cadence_mode=chat_cadence_mode,
        speaker_mode=expression_contract["speaker_mode"],
        epistemic_status=expression_contract["epistemic_status"],
        commitment_level=expression_contract["commitment_level"],
        must_include=expression_contract["must_include"],
        must_not_upgrade=expression_contract["must_not_upgrade"],
        tone_bounds=expression_contract["tone_bounds"],
        memory_claim_verdict=verdict,
        metadata=metadata_dict,
    )


def build_runtime_result_response_plan(result: Any, state: Any) -> ResponsePlan:
    reply_like = getattr(result, "reply", None) or result
    reply_metadata = dict(getattr(reply_like, "metadata", None) or {})
    runtime_status = getattr(result, "status", None) or getattr(reply_like, "status", None)
    delivery_kind = getattr(reply_like, "delivery_kind", None) or getattr(result, "delivery_kind", None) or (
        "progress" if runtime_status == "waiting_input" else "chat"
    )
    evidence_payload = _build_current_turn_evidence_payload(state)
    conversation_act = _build_conversation_act(state)
    has_run_items = bool(getattr(state, "get_run_items", lambda: [])())
    if runtime_status in {"completed_verified", "completed", "blocked", "failed"} and has_run_items:
        reply_authority = "host_terminal"
    elif runtime_status == "status_probe":
        reply_authority = "host_status"
    elif evidence_payload is not None:
        reply_authority = "host_evidence"
    elif runtime_status in {"completed_verified", "completed", "blocked", "failed"}:
        reply_authority = "host_terminal"
    else:
        reply_authority = "model_chat"

    reply_authority = str(reply_metadata.get("reply_authority") or reply_authority)
    conversation_act = str(reply_metadata.get("chat_act") or conversation_act).strip() or conversation_act
    expression_contract = _build_expression_contract(
        state,
        reply_authority=reply_authority,
        conversation_act=conversation_act,
        metadata=reply_metadata,
    )
    effective_restore = _resolve_restore_observation(state)
    current_session_grounding = _build_current_session_recall_grounding(state)
    gated_reply_text, verdict, final_authority = _apply_memory_claim_contract(
        getattr(reply_like, "reply_text", "") or "",
        kind=runtime_status or "runtime_result",
        reply_authority=reply_authority,
        restore_observation=effective_restore,
        current_session_grounding=current_session_grounding,
    )
    reply_origin = str(reply_metadata.get("reply_origin") or _infer_reply_origin(state, runtime_status, final_authority)).strip()
    chat_cadence_mode = _resolve_chat_cadence_mode(
        kind=runtime_status or "runtime_result",
        delivery_kind=delivery_kind,
        metadata=reply_metadata,
    )

    metadata = {
        "runtime_status": runtime_status,
        "task_status": getattr(state, "task_status", None),
        "conversation_act": conversation_act,
        "reply_origin": reply_origin,
        "chat_cadence_mode": chat_cadence_mode,
        "memory_claim_reason": verdict.reason,
        "memory_claim_allowed": verdict.allowed,
        "memory_claim_detected": verdict.claim_detected,
        "memory_claim_grounding_source": (
            current_session_grounding.authority_source if current_session_grounding is not None else None
        ),
    }
    if evidence_payload is not None:
        metadata["evidence_payload"] = evidence_payload
        metadata["evidence_binding_source_turn"] = evidence_payload.get("source_turn_id")
    recent_result_context = _build_current_turn_recent_result_context(
        state,
        runtime_status=runtime_status,
        reply_origin=reply_origin,
        delivery_kind=delivery_kind,
        reply_text=gated_reply_text,
    )
    if recent_result_context is not None:
        metadata["recent_result_context"] = recent_result_context
        metadata["result_binding_source_turn"] = recent_result_context.get("source_turn_id")
    if "chat_expression_hint" in reply_metadata:
        metadata["chat_expression_hint"] = dict(reply_metadata.get("chat_expression_hint") or {})
    if "response_tendency_summary" in reply_metadata:
        metadata["response_tendency_summary"] = dict(reply_metadata.get("response_tendency_summary") or {})
    if "chat_degradation" in reply_metadata:
        metadata["chat_degradation"] = dict(reply_metadata.get("chat_degradation") or {})
    if "degraded" in reply_metadata:
        metadata["degraded"] = bool(reply_metadata.get("degraded"))
    _apply_continuation_metadata(metadata, state)
    _apply_final_text_metadata(metadata, gated_reply_text)
    intent_contract_source = _build_intent_contract_source(
        state,
        reply_authority=final_authority,
        conversation_act=conversation_act,
        metadata=metadata,
        restore_observation=effective_restore,
    )
    metadata["intent_contract_source"] = intent_contract_source
    metadata["intent_contract_source_status"] = intent_contract_source.get("source_status")

    return ResponsePlan(
        kind=runtime_status or "runtime_result",
        reply_text=gated_reply_text,
        delivery_kind=delivery_kind,
        authority_source="response_contract.response_plan",
        reply_authority=final_authority,
        chat_cadence_mode=chat_cadence_mode,
        speaker_mode=expression_contract["speaker_mode"],
        epistemic_status=expression_contract["epistemic_status"],
        commitment_level=expression_contract["commitment_level"],
        must_include=expression_contract["must_include"],
        must_not_upgrade=expression_contract["must_not_upgrade"],
        tone_bounds=expression_contract["tone_bounds"],
        memory_claim_verdict=verdict,
        metadata=metadata,
    )


def build_status_response_plan(
    text: str,
    state: Any,
    *,
    assume_active: bool = False,
    restore_observation: Optional[PendingRestoreObservation] = None,
) -> ResponsePlan:
    reply_text = build_runtime_status_reply(state, assume_active=assume_active)
    effective_restore = _resolve_restore_observation(state, restore_observation=restore_observation)
    expression_contract = _build_expression_contract(
        state,
        reply_authority="host_status",
        conversation_act="status_probe",
        metadata={},
    )
    gated_reply_text, verdict, final_authority = _apply_memory_claim_contract(
        reply_text,
        kind="status_probe",
        reply_authority="host_status",
        restore_observation=effective_restore,
        current_session_grounding=_build_current_session_recall_grounding(state),
    )
    metadata = {
        "assume_active": assume_active,
        "memory_claim_reason": verdict.reason,
        "memory_claim_allowed": verdict.allowed,
        "memory_claim_detected": verdict.claim_detected,
        "conversation_act": "status_probe",
        "reply_origin": "status_mainline",
    }
    _apply_final_text_metadata(metadata, gated_reply_text)
    intent_contract_source = _build_intent_contract_source(
        state,
        reply_authority=final_authority,
        conversation_act="status_probe",
        metadata=metadata,
        restore_observation=effective_restore,
    )
    metadata["intent_contract_source"] = intent_contract_source
    metadata["intent_contract_source_status"] = intent_contract_source.get("source_status")
    return ResponsePlan(
        kind="status_probe",
        reply_text=gated_reply_text,
        delivery_kind="final",
        authority_source="response_contract.response_plan",
        reply_authority=final_authority,
        chat_cadence_mode=None,
        speaker_mode=expression_contract["speaker_mode"],
        epistemic_status=expression_contract["epistemic_status"],
        commitment_level=expression_contract["commitment_level"],
        must_include=expression_contract["must_include"],
        must_not_upgrade=expression_contract["must_not_upgrade"],
        tone_bounds=expression_contract["tone_bounds"],
        memory_claim_verdict=verdict,
        metadata=metadata,
    )


_SHELL_DIRECTORY_TOKENS = {"dir", "ls", "get-childitem", "gci"}
_SHELL_READ_TOKENS = {"type", "cat", "get-content", "gc", "more"}
_SHELL_SCAN_TOKENS = {"rg", "grep", "findstr", "find", "fd", "where"}
_DEFAULT_MUST_NOT_UPGRADE = {
    "epistemic_upgrade": True,
    "commitment_upgrade": True,
    "tone_upgrade": True,
}
_CHAT_CADENCE_MODES = {
    "reply_now_short",
    "reply_now_normal",
    "reply_now_expand",
    "hold_for_followup",
}


def _resolve_chat_cadence_mode(
    *,
    kind: str,
    delivery_kind: str,
    metadata: Dict[str, Any],
) -> Optional[str]:
    explicit = str(metadata.get("chat_cadence_mode") or "").strip()
    if explicit in _CHAT_CADENCE_MODES:
        return explicit

    hint = dict(metadata.get("chat_expression_hint") or {})
    reply_mode = str(hint.get("reply_mode") or "").strip()
    if reply_mode == "short":
        return "reply_now_short"
    if reply_mode == "expand":
        return "reply_now_expand"
    if reply_mode == "hold":
        return "hold_for_followup"

    normalized_kind = str(kind or "").strip()
    normalized_delivery = str(delivery_kind or "").strip()
    if normalized_kind == "chat" or normalized_delivery == "chat":
        return "reply_now_normal"
    return None


def _build_conversation_act(state: Any) -> str:
    if state is None:
        return "runtime_result"
    ingress_context = dict(getattr(state, "ingress_context", None) or {})
    existing = str(ingress_context.get("conversation_act") or "").strip()
    if existing:
        return existing
    interaction_kind = str(ingress_context.get("interaction_kind") or "").strip()
    if interaction_kind == "chat":
        return "chat"
    if interaction_kind == "wait":
        return "status_probe"
    return "runtime_result"


def _build_current_turn_evidence_payload(state: Any) -> Optional[Dict[str, Any]]:
    active_turn_id = str(getattr(state, "active_turn_id", "") or "").strip()
    tool_result_turn_id = str(getattr(state, "last_tool_result_turn_id", "") or "").strip()
    if not active_turn_id or active_turn_id != tool_result_turn_id:
        return None

    payload = dict(getattr(state, "last_tool_result", None) or {})
    if not payload or not bool(payload.get("success")):
        return None

    tool_name = str(payload.get("tool") or payload.get("tool_name") or "").strip().lower()
    metadata = dict(payload.get("metadata") or {})
    body = str(payload.get("stdout") or payload.get("output") or "").strip()
    if not tool_name or not body or body == "Command completed successfully":
        return None

    request_kind: Optional[str] = None
    target_path: Optional[str] = None

    if tool_name == "file":
        operation = str(metadata.get("operation") or "").strip().lower()
        if operation == "read":
            request_kind = "file_read"
        elif operation == "list":
            request_kind = "directory_listing"
        if request_kind:
            target_path = str(metadata.get("path") or "").strip() or None
    elif tool_name == "shell":
        command = str(metadata.get("command") or "").strip().lower()
        request_kind = _classify_shell_request_kind(command)
        if request_kind:
            target_path = str(metadata.get("path") or metadata.get("working_directory") or "").strip() or None

    if request_kind is None:
        return None

    return {
        "authority_source": "response_contract.response_plan",
        "tool_name": tool_name,
        "request_kind": request_kind,
        "target_path": target_path,
        "body": body,
        "truncated": bool(metadata.get("truncated") or payload.get("truncated")),
        "delivery_was_chunked": False,
        "source_turn_id": active_turn_id,
        "source_assistant_message_id": None,
        "delivered_at": None,
        "conversation_act": _build_conversation_act(state),
    }


def _looks_like_windows_path(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value or ""))


def _basename_from_path(path: Optional[str]) -> Optional[str]:
    text = str(path or "").strip()
    if not text:
        return None
    if _looks_like_windows_path(text):
        return PureWindowsPath(text).name or text
    return PurePosixPath(text).name or text


def _build_tool_result_summary(state: Any) -> Optional[Dict[str, Any]]:
    payload = dict(getattr(state, "last_tool_result", None) or {})
    if not payload:
        return None

    metadata = dict(payload.get("metadata") or {})
    summary: Dict[str, Any] = {
        "tool": payload.get("tool") or payload.get("tool_name"),
        "success": payload.get("success"),
        "exit_code": payload.get("exit_code"),
        "operation": metadata.get("operation"),
        "path": metadata.get("path"),
        "working_directory": metadata.get("working_directory"),
    }
    command = str(metadata.get("command") or "").strip()
    if command:
        summary["command_preview"] = command[:160]
    stdout = str(payload.get("stdout") or payload.get("output") or "").strip()
    if stdout:
        summary["stdout_preview"] = stdout[:200]
    summary = {key: value for key, value in summary.items() if value not in (None, "", [], {})}
    return summary or None


def _resolve_recent_result_target_path(state: Any) -> Optional[str]:
    tool_result = dict(getattr(state, "last_tool_result", None) or {})
    metadata = dict(tool_result.get("metadata") or {})
    for key in ("path", "target_path", "effective_path", "working_directory"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value

    run_items = list(getattr(state, "get_run_items", lambda: [])() or [])
    verified_items = [item for item in run_items if getattr(item, "status", None) == "verified"]
    candidate_items = verified_items or run_items[-1:]
    for item in reversed(candidate_items):
        canonical_path = str(getattr(item, "canonical_path", None) or "").strip()
        if canonical_path:
            return canonical_path

    ingress_context = dict(getattr(state, "ingress_context", None) or {})
    resolved_target = dict(ingress_context.get("resolved_target") or {})
    requested_output = dict(ingress_context.get("requested_output") or {})
    for value in (
        resolved_target.get("path"),
        requested_output.get("effective_path"),
        requested_output.get("target_path"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return None


def _build_current_turn_recent_result_context(
    state: Any,
    *,
    runtime_status: Any,
    reply_origin: str,
    delivery_kind: str,
    reply_text: str,
) -> Optional[Dict[str, Any]]:
    if str(reply_origin or "").strip() != "task_mainline":
        return None
    if str(runtime_status or "").strip() not in {"completed_verified", "completed", "blocked", "failed"}:
        return None

    target_path = _resolve_recent_result_target_path(state)
    tool_result_summary = _build_tool_result_summary(state)
    if not target_path and not tool_result_summary and not str(reply_text or "").strip():
        return None

    return {
        "authority_source": "response_contract.response_plan",
        "binding_kind": "recent_delivered_result",
        "source_turn_id": str(getattr(state, "active_turn_id", None) or "").strip() or None,
        "runtime_status": str(runtime_status or "").strip() or None,
        "reply_origin": "task_mainline",
        "delivery_kind": str(delivery_kind or "").strip() or None,
        "target_path": target_path,
        "target_name": _basename_from_path(target_path),
        "tool_result_summary": tool_result_summary or {},
        "reply_preview": str(reply_text or "").strip()[:200] or None,
    }


def _build_expression_contract(
    state: Any,
    *,
    reply_authority: str,
    conversation_act: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(metadata or {})

    if reply_authority == "model_chat":
        speaker_mode = "reflect"
        epistemic_status = _build_chat_epistemic_status(conversation_act)
        commitment_level = "soft"
        must_include = _build_chat_must_include(conversation_act)
        tone_bounds = _build_chat_tone_bounds(state, conversation_act)
    else:
        speaker_mode = "report"
        epistemic_status = "observed"
        commitment_level = "none"
        must_include = _build_host_must_include(reply_authority)
        tone_bounds = _build_host_tone_bounds(reply_authority)

    if metadata.get("speaker_mode"):
        speaker_mode = str(metadata["speaker_mode"]).strip() or speaker_mode
    if metadata.get("epistemic_status"):
        epistemic_status = str(metadata["epistemic_status"]).strip() or epistemic_status
    if metadata.get("commitment_level"):
        commitment_level = str(metadata["commitment_level"]).strip() or commitment_level

    raw_must_include = metadata.get("must_include")
    if raw_must_include is not None:
        must_include = tuple(str(item).strip() for item in raw_must_include if str(item).strip())

    raw_must_not_upgrade = metadata.get("must_not_upgrade")
    if isinstance(raw_must_not_upgrade, dict):
        must_not_upgrade = {
            key: bool(value)
            for key, value in {**_DEFAULT_MUST_NOT_UPGRADE, **raw_must_not_upgrade}.items()
        }
    else:
        must_not_upgrade = dict(_DEFAULT_MUST_NOT_UPGRADE)

    raw_tone_bounds = metadata.get("tone_bounds")
    if isinstance(raw_tone_bounds, dict):
        tone_bounds = dict(raw_tone_bounds)

    return {
        "speaker_mode": speaker_mode,
        "epistemic_status": epistemic_status,
        "commitment_level": commitment_level,
        "must_include": tuple(must_include),
        "must_not_upgrade": must_not_upgrade,
        "tone_bounds": tone_bounds,
    }


def _build_chat_epistemic_status(conversation_act: str) -> str:
    # Reflective chat is allowed to use lightweight inference markers such as
    # "可能/大概/我想", but should still be blocked from definite claims.
    if conversation_act in {
        "presence_check",
        "social_keepalive",
        "light_chitchat",
        "tone_feedback",
        "task_bridge_request",
        "chat",
    }:
        return "interpreted"
    return "interpreted"


def _build_intent_contract_source(
    state: Any,
    *,
    reply_authority: str,
    conversation_act: str,
    metadata: Optional[Dict[str, Any]] = None,
    restore_observation: Optional[PendingRestoreObservation] = None,
) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    explicit_source = metadata.get("intent_contract_source")
    source_status = "default_host_contract"
    raw_allowed_claims: Any = metadata.get("allowed_claims")
    raw_forbidden_claims: Any = metadata.get("forbidden_claims")
    raw_grounding: Any = metadata.get("grounding")

    if isinstance(explicit_source, dict):
        source_status = str(explicit_source.get("source_status") or "explicit_metadata")
        raw_allowed_claims = explicit_source.get("allowed_claims")
        raw_forbidden_claims = explicit_source.get("forbidden_claims")
        raw_grounding = explicit_source.get("grounding")
    elif any(key in metadata for key in ("allowed_claims", "forbidden_claims", "grounding")):
        source_status = "normalized_metadata_inputs"

    allowed_claims = _normalize_allowed_claims(raw_allowed_claims)
    forbidden_claims = _normalize_forbidden_claims(raw_forbidden_claims)
    grounding, grounding_source = _resolve_intent_grounding(
        state,
        raw_grounding=raw_grounding,
        reply_authority=reply_authority,
        conversation_act=conversation_act,
        restore_observation=restore_observation,
    )
    return {
        "authority_source": "response_contract.intent_contract_source",
        "source_status": source_status,
        "allowed_claims": allowed_claims,
        "forbidden_claims": forbidden_claims,
        "grounding": grounding,
        "grounding_source": grounding_source,
    }


def _normalize_allowed_claims(raw_allowed_claims: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in list(raw_allowed_claims or []):
        if isinstance(item, dict):
            claim = str(item.get("claim") or "").strip()
            if not claim:
                continue
            normalized.append(
                {
                    "claim": claim,
                    "source": str(item.get("source") or "response_plan.metadata").strip() or "response_plan.metadata",
                }
            )
            continue
        claim = str(item or "").strip()
        if claim:
            normalized.append({"claim": claim, "source": "response_plan.metadata"})
    return normalized


def _normalize_forbidden_claims(raw_forbidden_claims: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in list(raw_forbidden_claims or []):
        if isinstance(item, dict):
            pattern = str(item.get("pattern") or "").strip()
            if not pattern:
                continue
            normalized.append(
                {
                    "pattern": pattern,
                    "reason": str(item.get("reason") or "explicit_forbidden_claim").strip() or "explicit_forbidden_claim",
                    "severity": str(item.get("severity") or "ERROR").strip() or "ERROR",
                }
            )
            continue
        pattern = str(item or "").strip()
        if pattern:
            normalized.append(
                {
                    "pattern": pattern,
                    "reason": "explicit_forbidden_claim",
                    "severity": "ERROR",
                }
            )
    return normalized


def _resolve_intent_grounding(
    state: Any,
    *,
    raw_grounding: Any,
    reply_authority: str,
    conversation_act: str,
    restore_observation: Optional[PendingRestoreObservation],
) -> tuple[Dict[str, Any], str]:
    if isinstance(raw_grounding, dict) and raw_grounding:
        return dict(raw_grounding), "metadata.grounding"

    proto_self_grounding = _extract_proto_self_intent_grounding(state)
    if proto_self_grounding:
        return proto_self_grounding, "proto_self_context.intent_contract"

    ingress_context = dict(getattr(state, "ingress_context", None) or {}) if state is not None else {}
    ingress_grounding = ingress_context.get("response_grounding")
    if isinstance(ingress_grounding, dict) and ingress_grounding:
        return dict(ingress_grounding), "ingress_context.response_grounding"

    grounding: Dict[str, Any] = {
        "reply_scope": {
            "reply_authority": reply_authority,
            "conversation_act": conversation_act,
            "interaction_kind": str(ingress_context.get("interaction_kind") or "").strip() or None,
            "parser_source": str(ingress_context.get("parser_source") or "").strip() or None,
            "primary_intent": str(ingress_context.get("primary_intent") or "").strip() or None,
        }
    }
    if restore_observation is not None:
        grounding["restore_observation"] = {
            "restore_status": restore_observation.restore_status,
            "authority_source": restore_observation.authority_source,
            "post_restore_first_turn": restore_observation.post_restore_first_turn,
        }
    if state is not None and hasattr(state, "build_active_task_summary"):
        active_task_summary = state.build_active_task_summary()
        if active_task_summary:
            grounding["active_task_summary"] = active_task_summary
    proto_self_context = dict(getattr(state, "proto_self_context", None) or {}) if state is not None else {}
    subject_profile = str(proto_self_context.get("subject_profile") or "").strip()
    if subject_profile:
        grounding["subject_profile"] = subject_profile
    return grounding, "host_expression_contract"


def _extract_proto_self_intent_grounding(state: Any) -> Dict[str, Any]:
    proto_self_context = dict(getattr(state, "proto_self_context", None) or {}) if state is not None else {}
    for key in ("finalized_result", "external_result", "idle_check"):
        payload = proto_self_context.get(key)
        if not isinstance(payload, dict):
            continue
        candidate = _extract_intent_grounding_from_payload(payload)
        if candidate:
            return candidate
    return {}


def _extract_intent_grounding_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    direct_contract = payload.get("intent_contract") or payload.get("response_intent_contract")
    if isinstance(direct_contract, dict):
        grounding = direct_contract.get("grounding")
        if isinstance(grounding, dict) and grounding:
            return dict(grounding)

    trace_payload = payload.get("trace_payload")
    if isinstance(trace_payload, dict):
        exec_result = trace_payload.get("exec_result")
        if isinstance(exec_result, dict):
            nested_contract = exec_result.get("intent_contract") or exec_result.get("response_intent_contract")
            if isinstance(nested_contract, dict):
                grounding = nested_contract.get("grounding")
                if isinstance(grounding, dict) and grounding:
                    return dict(grounding)
    return {}


def _build_chat_must_include(conversation_act: str) -> tuple[str, ...]:
    if conversation_act == "presence_check":
        return ("回应当前在线确认", "不主动拉回任务")
    if conversation_act == "tone_feedback":
        return ("先接住用户对语气或重复的反馈",)
    if conversation_act == "task_bridge_request":
        return ("只在用户明确要求时桥接到任务",)
    return ("回应当前聊天意图",)


def _build_host_must_include(reply_authority: str) -> tuple[str, ...]:
    if reply_authority == "host_evidence":
        return ("只基于当前证据回答",)
    if reply_authority == "host_status":
        return ("只基于当前运行状态回答",)
    if reply_authority == "host_terminal":
        return ("只基于当前已验证状态总结",)
    return ("维持宿主安全表达边界",)


def _build_chat_tone_bounds(state: Any, conversation_act: str) -> Dict[str, Any]:
    style_profile = {}
    if state is not None and hasattr(state, "get_chat_state"):
        chat_state = state.get_chat_state()
        style_profile = dict(getattr(chat_state, "style_profile", None) or {})

    dimensions = dict(style_profile.get("dimensions") or {})
    warmth = float(dimensions.get("warmth", 0.5) or 0.5)
    directness = float(dimensions.get("directness", 0.5) or 0.5)
    softness = float(dimensions.get("softness", 0.5) or 0.5)

    allowed_tones = []
    if warmth >= 0.55:
        allowed_tones.append("warm")
    if softness >= 0.55:
        allowed_tones.append("supportive")
    if directness >= 0.65:
        allowed_tones.append("direct")
    else:
        allowed_tones.append("cautious")
    if conversation_act == "tone_feedback":
        allowed_tones.append("repairing")
    if not allowed_tones:
        allowed_tones = ["natural", "responsive"]

    forbidden_tones = ["hostile", "defensive"]
    if conversation_act != "task_bridge_request":
        forbidden_tones.append("task_pushy")
    if softness >= 0.65:
        forbidden_tones.append("abrasive")

    intensity_cap = round(max(0.35, min(0.85, 0.45 + warmth * 0.25 + softness * 0.15)), 2)
    return {
        "intensity_cap": intensity_cap,
        "allowed_tones": _dedupe_strs(allowed_tones),
        "forbidden_tones": _dedupe_strs(forbidden_tones),
    }


def _build_host_tone_bounds(reply_authority: str) -> Dict[str, Any]:
    allowed_tones = ["clear", "neutral", "concise"]
    if reply_authority == "host_evidence":
        allowed_tones.append("verbatim")
    elif reply_authority == "host_terminal":
        allowed_tones.append("grounded")
    elif reply_authority == "host_status":
        allowed_tones.append("bounded")

    return {
        "intensity_cap": 0.45,
        "allowed_tones": _dedupe_strs(allowed_tones),
        "forbidden_tones": ["hostile", "speculative", "overclaiming"],
    }


def _resolve_restore_observation(
    state: Any,
    *,
    restore_observation: Optional[PendingRestoreObservation] = None,
) -> Optional[PendingRestoreObservation]:
    if restore_observation is not None:
        return restore_observation
    if state is None:
        return None

    ingress_context = dict(getattr(state, "ingress_context", None) or {})
    payload = ingress_context.get("restore_observation")
    if isinstance(payload, PendingRestoreObservation):
        return payload
    if isinstance(payload, dict) and payload.get("restore_status"):
        return PendingRestoreObservation(**payload)
    return None


def _build_current_session_recall_grounding(state: Any) -> Optional[CurrentSessionRecallGrounding]:
    if state is None or not hasattr(state, "get_chat_state"):
        return None
    chat_state = state.get_chat_state()
    return build_current_session_recall_grounding(
        recent_user_turns=list(getattr(chat_state, "recent_user_turns", None) or []),
        current_user_turn=str(getattr(state, "last_user_turn", "") or ""),
    )


def _apply_memory_claim_contract(
    reply_text: str,
    *,
    kind: str,
    reply_authority: str,
    restore_observation: Optional[PendingRestoreObservation],
    current_session_grounding: Optional[CurrentSessionRecallGrounding],
    explicit_verdict: Optional[MemoryClaimVerdict] = None,
) -> tuple[str, MemoryClaimVerdict, str]:
    verdict = explicit_verdict or evaluate_memory_claim(
        reply_text,
        restore_observation=restore_observation,
        current_session_grounding=current_session_grounding,
    )
    if verdict.allowed or not verdict.claim_detected:
        return str(reply_text or ""), verdict, reply_authority

    safe_text = _build_disallowed_memory_claim_reply(kind=kind, reply_authority=reply_authority)
    final_authority = "host_degraded_fallback" if reply_authority == "model_chat" else reply_authority
    return safe_text, verdict, final_authority


def _build_disallowed_memory_claim_reply(*, kind: str, reply_authority: str) -> str:
    if reply_authority == "model_chat" or kind == "chat":
        return "我先不把这件事说成已恢复或记住。你可以继续说。"
    if reply_authority == "host_status" or kind == "status_probe":
        return "当前还不能确认已恢复或已记住。"
    if reply_authority == "host_evidence":
        return "当前先按已观察到的内容回答，不追加已恢复或记住的说法。"
    return "当前还不能把这件事说成已恢复或已记住。"


def _dedupe_strs(values: Sequence[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _infer_reply_origin(state: Any, runtime_status: Optional[str], reply_authority: str) -> str:
    if reply_authority == "model_chat":
        return "chat_mainline"
    if reply_authority == "host_evidence":
        return "evidence_mainline"
    if reply_authority == "host_status":
        return "status_mainline"
    if reply_authority == "host_terminal":
        return "task_mainline"
    interaction_kind = str(((getattr(state, "ingress_context", None) or {}).get("interaction_kind") or "")).strip()
    if interaction_kind == "chat" and runtime_status == "chat":
        return "chat_mainline"
    if runtime_status == "status_probe":
        return "status_mainline"
    return "task_mainline"


def _classify_shell_request_kind(command: str) -> Optional[str]:
    if not command:
        return None
    tokens = set(re.findall(r"[a-z0-9_.-]+", command))
    if tokens & _SHELL_DIRECTORY_TOKENS:
        return "directory_listing"
    if tokens & _SHELL_READ_TOKENS:
        return "file_read"
    if tokens & _SHELL_SCAN_TOKENS:
        return "scan_results"
    return None
