from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, Optional

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
) -> ResponsePlan:
    return ResponsePlan(
        kind=kind,
        reply_text=reply_text,
        delivery_kind=delivery_kind,
        authority_source=authority_source,
        reply_authority=reply_authority,
        memory_claim_verdict=memory_claim_verdict,
        metadata=dict(metadata or {}),
    )


def build_runtime_result_response_plan(result: Any, state: Any) -> ResponsePlan:
    delivery_kind = getattr(result, "delivery_kind", None) or (
        "progress" if getattr(result, "status", None) == "waiting_input" else "chat"
    )
    evidence_payload = _build_current_turn_evidence_payload(state)
    conversation_act = _build_conversation_act(state)
    runtime_status = getattr(result, "status", None)
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

    metadata = {
        "runtime_status": runtime_status,
        "task_status": getattr(state, "task_status", None),
        "conversation_act": conversation_act,
    }
    if evidence_payload is not None:
        metadata["evidence_payload"] = evidence_payload
        metadata["evidence_binding_source_turn"] = evidence_payload.get("source_turn_id")

    return ResponsePlan(
        kind=runtime_status or "runtime_result",
        reply_text=getattr(result, "reply_text", "") or "",
        delivery_kind=delivery_kind,
        authority_source="response_contract.response_plan",
        reply_authority=reply_authority,
        metadata=metadata,
    )


def build_status_response_plan(
    text: str,
    state: Any,
    *,
    assume_active: bool = False,
    restore_observation: Optional[PendingRestoreObservation] = None,
) -> ResponsePlan:
    verdict = evaluate_memory_claim(text, restore_observation=restore_observation)
    reply_text = build_runtime_status_reply(state, assume_active=assume_active)
    return ResponsePlan(
        kind="status_probe",
        reply_text=reply_text,
        delivery_kind="final",
        authority_source="response_contract.response_plan",
        reply_authority="host_status",
        memory_claim_verdict=verdict,
        metadata={
            "assume_active": assume_active,
            "memory_claim_reason": verdict.reason,
            "memory_claim_allowed": verdict.allowed,
            "conversation_act": "status_probe",
        },
    )


_SHELL_DIRECTORY_TOKENS = {"dir", "ls", "get-childitem", "gci"}
_SHELL_READ_TOKENS = {"type", "cat", "get-content", "gc", "more"}
_SHELL_SCAN_TOKENS = {"rg", "grep", "findstr", "find", "fd", "where"}


def _build_conversation_act(state: Any) -> str:
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
