from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import logging

from openemotion.proto_self_v2.seed_schemas import SEED_SCHEMA_VERSION, SEED_SUBJECT_PROFILE

from app.risk_signal import (
    assess_message_risk_level,
    risk_level_from_external_result,
)
from .state import RuntimeV2State

logger = logging.getLogger(__name__)


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
        "active_task": state.task_status in {"running", "waiting_input"},
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
    }


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
    if result.status == "waiting_input":
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
) -> Dict[str, Any]:
    risk_level = assess_risk_level(user_input)
    restore_observation = (state.ingress_context or {}).get("restore_observation")
    schema_version = resolve_proto_self_schema_version(state)
    if schema_version == "proto_self.v2":
        ingress_context = state.ingress_context or {}
        subject_profile = resolve_proto_self_subject_profile(state)
        runtime_summary = {
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            "restore_observation": restore_observation,
        }
        runtime_summary.update(
            {
                k: v
                for k, v in _seed_runtime_summary(state).items()
                if v is not None
            }
        )
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
            "runtime_summary": {
                "runtime": "runtime_v2",
                "state_scope": "agent_global",
            },
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
        "runtime_summary": {
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **_seed_runtime_summary(state),
        },
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
) -> Optional[Dict[str, Any]]:
    if resolve_proto_self_schema_version(state) != "proto_self.v2":
        return None
    subject_profile = resolve_proto_self_subject_profile(state)
    if subject_profile != SEED_SUBJECT_PROFILE:
        return None
    return {
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
        "runtime_summary": {
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **_seed_runtime_summary(state),
        },
        "safety_context": {
            "risk_level": "low",
        },
        "executed_action_prev": None,
        "external_outcome": None,
        "intervention_context": {},
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
            "subject_profile": proto_self_result.get("subject_profile"),
            "policy_hint": proto_self_result.get("policy_hint"),
            "response_tendency": proto_self_result.get("response_tendency"),
            "reflection_note": proto_self_result.get("reflection_note"),
            "candidate_actions": proto_self_result.get("candidate_actions") or [],
            "governor_hint": (proto_self_result.get("policy_hint") or {}).get("governor_hint"),
        }
        state.record(
            "proto_self",
            {
                "subject_profile": proto_self_result.get("subject_profile"),
                "policy_hint": proto_self_result.get("policy_hint"),
                "candidate_actions": proto_self_result.get("candidate_actions") or [],
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
        )
        if not finalized_event:
            return
        finalized_result = self.adapter.handle_event(finalized_event)
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
        )
        if not idle_event:
            return
        idle_result = self.adapter.handle_event(idle_event)
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
        if idle_result.get("policy_hint"):
            state.proto_self_context["policy_hint"] = idle_result.get("policy_hint")
            state.proto_self_context["governor_hint"] = idle_result.get("policy_hint", {}).get("governor_hint")

    def capture_response_plan(self, *, result: Any, evidence_collector: Optional[Any] = None) -> None:
        collector = self._resolve_collector(evidence_collector)
        if collector is None:
            return
        collector.capture_response_plan(build_response_plan_payload(result=result))
