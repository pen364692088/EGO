from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, Optional, Sequence

from app.restore_runtime import PendingRestoreObservation
from app.runtime_v2.semantic_parser import build_runtime_status_reply

from .memory_claim_gate import MemoryClaimVerdict, evaluate_memory_claim


@dataclass(frozen=True)
class ResponsePlan:
    kind: str
    reply_text: str
    delivery_kind: str
    authority_source: str
    reply_authority: str
    speaker_mode: str = "reflect"
    epistemic_status: str = "uncertain"
    commitment_level: str = "soft"
    must_include: tuple[str, ...] = ()
    must_not_upgrade: Dict[str, bool] = field(default_factory=dict)
    tone_bounds: Dict[str, Any] = field(default_factory=dict)
    memory_claim_verdict: Optional[MemoryClaimVerdict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    effective_restore = _resolve_restore_observation(state, restore_observation=restore_observation)
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
        explicit_verdict=memory_claim_verdict,
    )
    metadata_dict.setdefault("conversation_act", conversation_act)
    metadata_dict.setdefault("reply_origin", _infer_reply_origin(state, kind, final_authority))
    metadata_dict["memory_claim_reason"] = verdict.reason
    metadata_dict["memory_claim_allowed"] = verdict.allowed
    metadata_dict["memory_claim_detected"] = verdict.claim_detected
    return ResponsePlan(
        kind=kind,
        reply_text=gated_reply_text,
        delivery_kind=delivery_kind,
        authority_source=authority_source,
        reply_authority=final_authority,
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
    gated_reply_text, verdict, final_authority = _apply_memory_claim_contract(
        getattr(reply_like, "reply_text", "") or "",
        kind=runtime_status or "runtime_result",
        reply_authority=reply_authority,
        restore_observation=_resolve_restore_observation(state),
    )
    reply_origin = str(reply_metadata.get("reply_origin") or _infer_reply_origin(state, runtime_status, final_authority)).strip()

    metadata = {
        "runtime_status": runtime_status,
        "task_status": getattr(state, "task_status", None),
        "conversation_act": conversation_act,
        "reply_origin": reply_origin,
        "memory_claim_reason": verdict.reason,
        "memory_claim_allowed": verdict.allowed,
        "memory_claim_detected": verdict.claim_detected,
    }
    if evidence_payload is not None:
        metadata["evidence_payload"] = evidence_payload
        metadata["evidence_binding_source_turn"] = evidence_payload.get("source_turn_id")

    return ResponsePlan(
        kind=runtime_status or "runtime_result",
        reply_text=gated_reply_text,
        delivery_kind=delivery_kind,
        authority_source="response_contract.response_plan",
        reply_authority=final_authority,
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
    )
    return ResponsePlan(
        kind="status_probe",
        reply_text=gated_reply_text,
        delivery_kind="final",
        authority_source="response_contract.response_plan",
        reply_authority=final_authority,
        speaker_mode=expression_contract["speaker_mode"],
        epistemic_status=expression_contract["epistemic_status"],
        commitment_level=expression_contract["commitment_level"],
        must_include=expression_contract["must_include"],
        must_not_upgrade=expression_contract["must_not_upgrade"],
        tone_bounds=expression_contract["tone_bounds"],
        memory_claim_verdict=verdict,
        metadata={
            "assume_active": assume_active,
            "memory_claim_reason": verdict.reason,
            "memory_claim_allowed": verdict.allowed,
            "memory_claim_detected": verdict.claim_detected,
            "conversation_act": "status_probe",
            "reply_origin": "status_mainline",
        },
    )


_SHELL_DIRECTORY_TOKENS = {"dir", "ls", "get-childitem", "gci"}
_SHELL_READ_TOKENS = {"type", "cat", "get-content", "gc", "more"}
_SHELL_SCAN_TOKENS = {"rg", "grep", "findstr", "find", "fd", "where"}
_DEFAULT_MUST_NOT_UPGRADE = {
    "epistemic_upgrade": True,
    "commitment_upgrade": True,
    "tone_upgrade": True,
}


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
        epistemic_status = "uncertain"
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


def _apply_memory_claim_contract(
    reply_text: str,
    *,
    kind: str,
    reply_authority: str,
    restore_observation: Optional[PendingRestoreObservation],
    explicit_verdict: Optional[MemoryClaimVerdict] = None,
) -> tuple[str, MemoryClaimVerdict, str]:
    verdict = explicit_verdict or evaluate_memory_claim(reply_text, restore_observation=restore_observation)
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
