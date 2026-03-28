from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import logging

from app.risk_signal import (
    assess_message_risk_level,
    risk_level_from_external_result,
)
from .state import RuntimeV2State

logger = logging.getLogger(__name__)


def assess_risk_level(user_input: str) -> str:
    return assess_message_risk_level(user_input)


def build_proto_self_ingress_event(
    *,
    session_id: str,
    turn_id: str,
    source: str,
    user_input: str,
    state: RuntimeV2State,
) -> Dict[str, Any]:
    risk_level = assess_risk_level(user_input)
    restore_observation = (state.ingress_context or {}).get("restore_observation")
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
) -> Dict[str, Any]:
    failed = not tool_result.get("success")
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
    return payload


@dataclass
class RuntimeV2ProtoSelfRuntime:
    adapter: Any
    trace_bridge: Any = None
    evidence_collector_factory: Optional[Any] = None

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
        )
        proto_self_result = self.adapter.handle_event(proto_self_event)
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
            "policy_hint": proto_self_result.get("policy_hint"),
            "response_tendency": proto_self_result.get("response_tendency"),
            "reflection_note": proto_self_result.get("reflection_note"),
        }
        state.record(
            "proto_self",
            {
                "policy_hint": proto_self_result.get("policy_hint"),
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
        )
        external_result = self.adapter.handle_event(external_result_event)
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
        if external_result.get("reflection_note"):
            state.record(
                "proto_self_reflection",
                {
                    "trigger": external_result.get("reflection_note", {}).get("trigger"),
                    "diagnosis": external_result.get("reflection_note", {}).get("diagnosis"),
                },
            )

    def capture_response_plan(self, *, result: Any, evidence_collector: Optional[Any] = None) -> None:
        collector = self._resolve_collector(evidence_collector)
        if collector is None:
            return
        collector.capture_response_plan(build_response_plan_payload(result=result))
