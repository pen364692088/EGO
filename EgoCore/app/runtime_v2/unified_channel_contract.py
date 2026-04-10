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
    pre_runtime_action = bridge.plan_pre_runtime(decision, state)
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
]
