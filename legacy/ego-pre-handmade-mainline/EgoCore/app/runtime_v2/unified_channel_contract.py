from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.runtime_v2.state import RuntimeV2State
from app.telegram_runtime_bridge import (
    TelegramDeliveryAction,
    TelegramIngressDecision,
    TelegramPreRuntimeAction,
    TelegramRuntimeBridge,
)
from app.telegram_runtime_result import TelegramTurnResult


@dataclass
class UnifiedIngressRequest:
    channel: str
    source_kind: str
    session_key: str
    user_input: str
    raw_event: Dict[str, Any]
    transport_meta: Dict[str, Any] = field(default_factory=dict)
    extra_context: Optional[str] = None

    @property
    def effective_user_input(self) -> str:
        if self.extra_context:
            return f"{self.user_input}\n\n{self.extra_context}"
        return self.user_input


@dataclass
class UnifiedIngressBundle:
    request: UnifiedIngressRequest
    semantic_decision: TelegramIngressDecision
    ingress_context: Dict[str, Any]
    pre_runtime_action: TelegramPreRuntimeAction
    normalized_turn_obj: Optional[Any] = None

    @property
    def normalized_turn(self) -> Optional[Dict[str, Any]]:
        if self.normalized_turn_obj is None:
            return None
        to_dict = getattr(self.normalized_turn_obj, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        return None

    @property
    def runtime_action(self) -> Optional[str]:
        return getattr(self.semantic_decision, "_runtime_action", None)


@dataclass
class UnifiedTurnResult:
    status: str
    state: RuntimeV2State
    reply_text: str
    delivery_kind: Optional[str]
    request: Optional[UnifiedIngressRequest] = None
    ingress: Optional[UnifiedIngressBundle] = None
    response_plan: Any = None
    output_verdict: Any = None
    openemotion_result: Optional[Dict[str, Any]] = None
    proto_self_context: Optional[Dict[str, Any]] = None
    checkpoint_payload: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    runtime_result: Optional[TelegramTurnResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedEgressEnvelope:
    should_send: bool
    user_visible_text: str
    delivery_kind: Optional[str]
    response_plan: Any = None
    output_verdict: Any = None
    transport_meta: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


HOST_CONTRACT_SNAPSHOT_VERSION = "unified_host_contract.v1"


def _trim_contract_text(value: Any, *, limit: int = 280) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _compact_response_plan_metadata_for_contract(metadata: Optional[dict]) -> Dict[str, Any]:
    source = dict(metadata or {})
    compact: Dict[str, Any] = {}
    if source.get("conversation_act"):
        compact["conversation_act"] = source.get("conversation_act")
    if source.get("matched_rule_ids"):
        compact["matched_rule_ids"] = list(source.get("matched_rule_ids") or [])
    if source.get("enforcement") is not None:
        compact["enforcement"] = source.get("enforcement")
    if source.get("rule_enforcement") is not None:
        compact["rule_enforcement"] = dict(source.get("rule_enforcement") or {})
    if source.get("recent_result_binding") is not None:
        compact["recent_result_binding"] = bool(source.get("recent_result_binding"))
    if source.get("correction_context") is not None:
        compact["correction_context"] = bool(source.get("correction_context"))
    if source.get("pending_result_continuation"):
        compact["pending_result_continuation"] = dict(source.get("pending_result_continuation") or {})
    if source.get("chat_expression_hint"):
        compact["chat_expression_hint"] = dict(source.get("chat_expression_hint") or {})
    if source.get("response_tendency_summary"):
        compact["response_tendency_summary"] = dict(source.get("response_tendency_summary") or {})
    if source.get("chat_degradation"):
        compact["chat_degradation"] = dict(source.get("chat_degradation") or {})
    return compact


def _compact_ingress_context_for_contract(ingress_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(ingress_context or {})
    return {
        "runtime_action": source.get("runtime_action"),
        "request_mode": source.get("request_mode"),
        "interaction_kind": source.get("interaction_kind"),
        "conversation_act": source.get("conversation_act"),
        "parser_source": source.get("parser_source"),
        "primary_intent": source.get("primary_intent"),
        "recent_result_binding": bool(source.get("recent_result_binding")),
        "correction_context": bool(source.get("correction_context")),
        "resolved_target": dict(source.get("resolved_target") or {}),
        "requested_output": dict(source.get("requested_output") or {}),
    }


def _extract_trace_reference(
    proto_self_context: Optional[Dict[str, Any]],
    openemotion_result: Optional[Dict[str, Any]],
) -> Optional[str]:
    candidates = [dict(openemotion_result or {})]
    source = dict(proto_self_context or {})
    if isinstance(source.get("finalized_result"), dict):
        candidates.append(dict(source.get("finalized_result") or {}))
    if isinstance(source.get("external_result"), dict):
        candidates.append(dict(source.get("external_result") or {}))
    for candidate in candidates:
        trace_payload = dict(candidate.get("trace_payload") or {})
        reference = str(trace_payload.get("update_packet_hash") or "").strip()
        if reference:
            return reference
    return None


def _trace_payload_present(
    proto_self_context: Optional[Dict[str, Any]],
    openemotion_result: Optional[Dict[str, Any]],
) -> bool:
    source = dict(proto_self_context or {})
    candidates = [dict(openemotion_result or {})]
    if isinstance(source.get("finalized_result"), dict):
        candidates.append(dict(source.get("finalized_result") or {}))
    if isinstance(source.get("external_result"), dict):
        candidates.append(dict(source.get("external_result") or {}))
    for candidate in candidates:
        if isinstance(candidate.get("trace_payload"), dict) and candidate.get("trace_payload"):
            return True
    return False


def _compact_proto_self_context_for_contract(
    proto_self_context: Optional[Dict[str, Any]],
    openemotion_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    source = dict(proto_self_context or {})
    return {
        "available": bool(source),
        "policy_hint": dict(source.get("policy_hint") or {}),
        "response_tendency": dict(source.get("response_tendency") or {}),
        "social_policy_hints": dict(source.get("social_policy_hints") or {}),
        "embodied_policy_hints": dict(source.get("embodied_policy_hints") or {}),
        "integrated_policy_hints": dict(source.get("integrated_policy_hints") or {}),
        "initiative_policy_hints": dict(source.get("initiative_policy_hints") or {}),
        "chat_cadence_mode": source.get("chat_cadence_mode"),
        "response_tendency_summary": dict(source.get("response_tendency_summary") or {}),
        "candidate_actions_count": len(list(source.get("candidate_actions") or [])),
        "finalized_result_present": isinstance(source.get("finalized_result"), dict),
        "external_result_present": isinstance(source.get("external_result"), dict),
        "trace_payload_present": _trace_payload_present(source, openemotion_result),
        "trace_reference": _extract_trace_reference(source, openemotion_result),
    }


def build_host_contract_snapshot(
    *,
    request: Optional[UnifiedIngressRequest] = None,
    ingress: Optional[UnifiedIngressBundle] = None,
    turn_result: Optional[UnifiedTurnResult] = None,
    egress: Optional[UnifiedEgressEnvelope] = None,
) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {"contract_version": HOST_CONTRACT_SNAPSHOT_VERSION}

    if request is not None:
        snapshot["adapter"] = {
            "channel": request.channel,
            "source_kind": request.source_kind,
            "raw_event_present": bool(request.raw_event),
            "transport_meta": dict(request.transport_meta or {}),
        }
        snapshot["request"] = {
            "session_key": request.session_key,
            "user_input": request.user_input,
            "effective_user_input": request.effective_user_input,
        }

    if ingress is not None:
        snapshot["ingress"] = {
            **_compact_ingress_context_for_contract(ingress.ingress_context),
            "normalized_turn": ingress.normalized_turn,
            "pre_runtime": {
                "should_return_early": bool(getattr(ingress.pre_runtime_action, "should_return_early", False)),
                "force_waiting_input": bool(getattr(ingress.pre_runtime_action, "force_waiting_input", False)),
                "direct_reply_text": _trim_contract_text(getattr(ingress.pre_runtime_action, "direct_reply_text", None)),
                "waiting_input_text": _trim_contract_text(getattr(ingress.pre_runtime_action, "waiting_input_text", None)),
                "rule_enforcement": dict(getattr(ingress.pre_runtime_action, "rule_enforcement", None) or {}),
            },
        }

    if turn_result is not None:
        response_plan = turn_result.response_plan
        output_verdict = turn_result.output_verdict
        response_metadata = getattr(response_plan, "metadata", None) if response_plan is not None else None
        runtime_reply_metadata = dict(
            getattr(getattr(turn_result.runtime_result, "reply", None), "metadata", None) or {}
        )
        snapshot["turn"] = {
            "status": turn_result.status,
            "reply_text": turn_result.reply_text,
            "delivery_kind": turn_result.delivery_kind,
            "finish_reason": turn_result.finish_reason,
            "reply_authority": getattr(response_plan, "reply_authority", None)
            or getattr(output_verdict, "applied_authority", None),
            "authority_source": getattr(response_plan, "authority_source", None),
            "response_plan": None
            if response_plan is None
            else {
                "kind": getattr(response_plan, "kind", None),
                "delivery_kind": getattr(response_plan, "delivery_kind", None),
                "authority_source": getattr(response_plan, "authority_source", None),
                "reply_authority": getattr(response_plan, "reply_authority", None),
                "chat_cadence_mode": getattr(response_plan, "chat_cadence_mode", None),
                "reply_text_preview": _trim_contract_text(getattr(response_plan, "reply_text", None)),
                "metadata": _compact_response_plan_metadata_for_contract(response_metadata),
            },
            "output_verdict": None
            if output_verdict is None
            else {
                "passed": bool(getattr(output_verdict, "passed", False)),
                "reason": getattr(output_verdict, "reason", None),
                "delivery_kind": getattr(output_verdict, "delivery_kind", None),
                "applied_authority": getattr(output_verdict, "applied_authority", None),
                "reply_origin": getattr(output_verdict, "reply_origin", None),
                "intent_gate_status": getattr(output_verdict, "intent_gate_status", None),
                "intent_gate_reason": getattr(output_verdict, "intent_gate_reason", None),
                "reply_text_preview": _trim_contract_text(getattr(output_verdict, "reply_text", None)),
            },
            "response_tendency_summary": dict(
                runtime_reply_metadata.get("response_tendency_summary")
                or ((response_metadata or {}).get("response_tendency_summary") if isinstance(response_metadata, dict) else {})
                or {}
            ),
            "chat_cadence_mode": (
                getattr(response_plan, "chat_cadence_mode", None)
                or runtime_reply_metadata.get("chat_cadence_mode")
            ),
            "proto_self_context": _compact_proto_self_context_for_contract(
                turn_result.proto_self_context,
                turn_result.openemotion_result,
            ),
        }

    if egress is not None:
        snapshot["egress"] = {
            "should_send": bool(egress.should_send),
            "user_visible_text": egress.user_visible_text,
            "delivery_kind": egress.delivery_kind,
            "transport_meta": dict(egress.transport_meta or {}),
        }

    return snapshot


def _collect_snapshot_diffs(left: Any, right: Any, *, path: str = "") -> list[Dict[str, Any]]:
    diffs: list[Dict[str, Any]] = []
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left.keys()) | set(right.keys()))
        for key in keys:
            next_path = f"{path}.{key}" if path else str(key)
            if key not in left:
                diffs.append({"path": next_path, "left": "__missing__", "right": deepcopy(right.get(key))})
                continue
            if key not in right:
                diffs.append({"path": next_path, "left": deepcopy(left.get(key)), "right": "__missing__"})
                continue
            diffs.extend(_collect_snapshot_diffs(left.get(key), right.get(key), path=next_path))
        return diffs
    if isinstance(left, list) and isinstance(right, list):
        if left != right:
            diffs.append({"path": path, "left": deepcopy(left), "right": deepcopy(right)})
        return diffs
    if left != right:
        diffs.append({"path": path, "left": deepcopy(left), "right": deepcopy(right)})
    return diffs


def compare_host_contract_snapshots(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    left_snapshot = dict(left or {})
    right_snapshot = dict(right or {})
    left_adapter = dict(left_snapshot.pop("adapter", {}) or {})
    right_adapter = dict(right_snapshot.pop("adapter", {}) or {})
    left_egress = dict(left_snapshot.get("egress") or {})
    right_egress = dict(right_snapshot.get("egress") or {})
    if "transport_meta" in left_egress or "transport_meta" in right_egress:
        left_egress.pop("transport_meta", None)
        right_egress.pop("transport_meta", None)
        if left_egress:
            left_snapshot["egress"] = left_egress
        else:
            left_snapshot.pop("egress", None)
        if right_egress:
            right_snapshot["egress"] = right_egress
        else:
            right_snapshot.pop("egress", None)
    unexpected_diffs = _collect_snapshot_diffs(left_snapshot, right_snapshot)
    return {
        "match": not unexpected_diffs,
        "allowed_adapter_fields": [
            "adapter.channel",
            "adapter.source_kind",
            "adapter.raw_event_present",
            "adapter.transport_meta",
            "egress.transport_meta",
        ],
        "left_adapter": left_adapter,
        "right_adapter": right_adapter,
        "unexpected_diffs": unexpected_diffs,
    }


def build_telegram_transport_meta(
    *,
    chat_id: Optional[int],
    user_id: Optional[int],
    username: Optional[str],
    message_id: Optional[int],
) -> Dict[str, Any]:
    return {
        "chat_id": chat_id,
        "user_id": user_id,
        "username": username,
        "message_id": message_id,
    }


def build_dashboard_transport_meta(
    *,
    session_name: str,
    message_id: Optional[int],
    client: str = "dashboard_local",
) -> Dict[str, Any]:
    return {
        "client": client,
        "session_name": session_name,
        "message_id": message_id,
    }


def build_telegram_unified_request(
    *,
    session_key: str,
    text: str,
    chat_id: Optional[int],
    user_id: Optional[int],
    username: Optional[str],
    message_id: Optional[int],
    source_kind: str,
    raw_event: Optional[Dict[str, Any]] = None,
    extra_context: Optional[str] = None,
) -> UnifiedIngressRequest:
    event = dict(raw_event or {})
    if not event:
        event = {
            "update_id": message_id,
            "message": {
                "message_id": message_id,
                "date": datetime.now(timezone.utc).isoformat(),
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": user_id, "username": username},
                "text": text,
            },
        }
    return UnifiedIngressRequest(
        channel="telegram",
        source_kind=source_kind,
        session_key=session_key,
        user_input=text,
        raw_event=event,
        transport_meta=build_telegram_transport_meta(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            message_id=message_id,
        ),
        extra_context=extra_context,
    )


def build_dashboard_unified_request(
    *,
    session_key: str,
    session_name: str,
    text: str,
    message_id: Optional[int],
    source_kind: str,
    raw_event: Optional[Dict[str, Any]] = None,
    extra_context: Optional[str] = None,
) -> UnifiedIngressRequest:
    event = dict(raw_event or {})
    if not event:
        event = {
            "dashboard_chat": {
                "session_id": session_key,
                "session_name": session_name,
                "message_id": message_id,
                "text": text,
                "source_kind": source_kind,
            }
        }
    return UnifiedIngressRequest(
        channel="api",
        source_kind=source_kind,
        session_key=session_key,
        user_input=text,
        raw_event=event,
        transport_meta=build_dashboard_transport_meta(
            session_name=session_name,
            message_id=message_id,
        ),
        extra_context=extra_context,
    )


async def build_unified_ingress(
    request: UnifiedIngressRequest,
    state: RuntimeV2State,
    *,
    bridge: TelegramRuntimeBridge,
    llm_client: Any = None,
) -> UnifiedIngressBundle:
    decision = await bridge.inspect_ingress_semantic(
        request.effective_user_input,
        state,
        llm_client=llm_client,
    )
    ingress_context = bridge.build_ingress_context(decision, state)
    state.ingress_context = dict(ingress_context or {})
    pre_runtime_action = bridge.plan_pre_runtime(decision, state)
    ingress_context = dict(state.ingress_context or ingress_context or {})
    return UnifiedIngressBundle(
        request=request,
        semantic_decision=decision,
        ingress_context=ingress_context,
        pre_runtime_action=pre_runtime_action,
        normalized_turn_obj=getattr(decision, "_normalized_turn", None),
    )


def build_unified_turn_result(
    *,
    state: RuntimeV2State,
    runtime_result: TelegramTurnResult,
    request: Optional[UnifiedIngressRequest] = None,
    ingress: Optional[UnifiedIngressBundle] = None,
    response_plan: Any = None,
    output_verdict: Any = None,
    openemotion_result: Optional[Dict[str, Any]] = None,
    proto_self_context: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> UnifiedTurnResult:
    if openemotion_result is None:
        finalized_result = dict((state.proto_self_context or {}).get("finalized_result") or {})
        external_result = dict((state.proto_self_context or {}).get("external_result") or {})
        openemotion_result = finalized_result or external_result or None
    if proto_self_context is None:
        proto_self_context = deepcopy(state.proto_self_context or {})
    return UnifiedTurnResult(
        status=runtime_result.status,
        state=state,
        reply_text=runtime_result.reply_text,
        delivery_kind=runtime_result.delivery_kind,
        request=request,
        ingress=ingress,
        response_plan=response_plan,
        output_verdict=output_verdict,
        openemotion_result=openemotion_result,
        proto_self_context=proto_self_context,
        checkpoint_payload=runtime_result.checkpoint_payload,
        finish_reason=runtime_result.finish_reason,
        runtime_result=runtime_result,
        metadata=dict(metadata or {}),
    )


def build_unified_egress(
    turn_result: UnifiedTurnResult,
    state: RuntimeV2State,
    *,
    bridge: Optional[TelegramRuntimeBridge] = None,
    is_challenge_turn: bool = False,
    delivery_action: Optional[TelegramDeliveryAction] = None,
    transport_meta: Optional[Dict[str, Any]] = None,
) -> UnifiedEgressEnvelope:
    if delivery_action is None and bridge is not None and turn_result.runtime_result is not None:
        delivery_action = bridge.plan_delivery(turn_result.runtime_result, state, is_challenge_turn)
    if delivery_action is not None:
        should_send = bool(delivery_action.should_send)
        user_visible_text = str(delivery_action.text or "")
        delivery_kind = turn_result.delivery_kind or getattr(delivery_action, "delivery_kind", None)
    else:
        user_visible_text = str(turn_result.reply_text or "")
        should_send = bool(user_visible_text)
        delivery_kind = turn_result.delivery_kind
    envelope_transport_meta = dict(turn_result.request.transport_meta if turn_result.request else {})
    if transport_meta:
        envelope_transport_meta.update(dict(transport_meta))
    return UnifiedEgressEnvelope(
        should_send=should_send,
        user_visible_text=user_visible_text,
        delivery_kind=delivery_kind,
        response_plan=turn_result.response_plan,
        output_verdict=turn_result.output_verdict,
        transport_meta=envelope_transport_meta,
        metadata=dict(turn_result.metadata or {}),
    )


__all__ = [
    "UnifiedIngressRequest",
    "UnifiedIngressBundle",
    "UnifiedTurnResult",
    "UnifiedEgressEnvelope",
    "build_telegram_transport_meta",
    "build_dashboard_transport_meta",
    "build_telegram_unified_request",
    "build_dashboard_unified_request",
    "build_unified_ingress",
    "build_unified_turn_result",
    "build_unified_egress",
    "HOST_CONTRACT_SNAPSHOT_VERSION",
    "build_host_contract_snapshot",
    "compare_host_contract_snapshots",
]
