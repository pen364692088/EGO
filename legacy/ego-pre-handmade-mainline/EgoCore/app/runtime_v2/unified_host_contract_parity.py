from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from types import MethodType
from typing import Any, Dict, List, Optional

from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE

from app.dashboard.chat_service import DashboardChatService
from app.openemotion_hooks.subject_gate import SubjectGateVerdict
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.unified_channel_contract import (
    build_host_contract_snapshot,
    build_telegram_transport_meta,
    build_telegram_unified_request,
    build_unified_egress,
    build_unified_ingress,
    build_unified_turn_result,
    compare_host_contract_snapshots,
)
from app.telegram_bot import TelegramBot
from app.telegram_runtime_bridge import TelegramPreRuntimeAction, TelegramRuntimeBridge
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


@dataclass(frozen=True)
class ParityCase:
    case_id: str
    text: str
    expected_mode: str
    expectation: str


PARITY_WINDOWS: Dict[str, List[ParityCase]] = {
    "ordinary_chat_window": [
        ParityCase("ordinary_hello", "你好", "reply_now_normal", "runtime_chat"),
        ParityCase("ordinary_stuck", "我现在有点卡住了，你先帮我理一下", "reply_now_expand", "runtime_chat"),
        ParityCase("ordinary_continue", "继续", "reply_now_short", "runtime_chat"),
        ParityCase("ordinary_why", "你刚才为什么那样回答", "reply_now_normal", "runtime_chat"),
    ],
    "hold_probe_window": [
        ParityCase("hold_probe", "我先消化一下", "hold_for_followup", "runtime_chat_hold"),
    ],
    "direct_reply_window": [
        ParityCase("pre_runtime_direct_reply", "先给我一个预检结论", "reply_now_normal", "pre_runtime_direct_reply"),
    ],
}


class _AllowSubjectGate:
    def process_ingress(self, **kwargs):
        return SubjectGateVerdict.allow(stage="ingress")

    def finalize_host_owned_result(self, **kwargs):
        return SubjectGateVerdict.allow(stage="response_plan")


class _DeterministicParityRunner:
    def __init__(self, case_profiles: Dict[str, Dict[str, Any]]) -> None:
        self.case_profiles = case_profiles

    async def run_turn(
        self,
        *,
        session_key: str,
        user_input: str,
        state,
        source: str = "telegram",
        evidence_collector=None,
    ):
        profile = dict(self.case_profiles.get(str(user_input), {}))
        reply_text = str(profile.get("reply_text") or f"echo: {user_input}")
        reply_mode = str(profile.get("reply_mode") or "normal")
        response_tendency_summary = dict(profile.get("response_tendency_summary") or {})
        chat_expression_hint = dict(profile.get("chat_expression_hint") or {"reply_mode": reply_mode})
        trace_reference = str(profile.get("trace_reference") or f"trace:{session_key}:{len(str(user_input))}")

        state.task_status = "chat"
        state.waiting_for_user_input = False
        state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
        state.proto_self_context = {
            "policy_hint": dict(profile.get("policy_hint") or {"delivery_mode": "bounded_chat"}),
            "response_tendency": dict(
                profile.get("response_tendency")
                or {
                    "preferred_mode": response_tendency_summary.get("preferred_mode") or "ask",
                    "preferred_tone": response_tendency_summary.get("preferred_tone") or "supportive",
                    "suggested_next_step": response_tendency_summary.get("suggested_next_step") or "clarify",
                }
            ),
            "social_policy_hints": dict(profile.get("social_policy_hints") or {"repair_bias": "elevated"}),
            "embodied_policy_hints": dict(profile.get("embodied_policy_hints") or {"resource_bias": "conserve"}),
            "integrated_policy_hints": dict(profile.get("integrated_policy_hints") or {"selected_priority": "guard"}),
            "initiative_policy_hints": dict(profile.get("initiative_policy_hints") or {"initiative_priority": "hold"}),
            "candidate_actions": list(profile.get("candidate_actions") or []),
            "finalized_result": {
                "trace_payload": {
                    "update_packet_hash": trace_reference,
                }
            },
        }

        return TelegramTurnResult(
            status="chat",
            state=state,
            reply=TelegramTurnReply(
                reply_text=reply_text,
                delivery_kind="chat",
                status="chat",
                metadata={
                    "reply_origin": "chat_mainline",
                    "reply_authority": "model_chat",
                    "chat_expression_hint": chat_expression_hint,
                    "response_tendency_summary": response_tendency_summary,
                    "chat_cadence_mode": profile.get("chat_cadence_mode"),
                },
            ),
        )


def _patch_bridge_for_parity(
    bridge: TelegramRuntimeBridge,
    *,
    direct_reply_text: str,
) -> None:
    original_plan_pre_runtime = bridge.plan_pre_runtime

    async def fake_semantic(self, text, state, llm_client=None):
        decision = self.inspect_ingress(text, state)
        setattr(decision, "_parity_user_input", text)
        return decision

    def fake_plan_pre_runtime(self, decision, state):
        text = str(getattr(decision, "_parity_user_input", "") or "")
        if text == direct_reply_text:
            return TelegramPreRuntimeAction(
                should_return_early=True,
                direct_reply_text="这是预检结论：当前统一宿主 contract 已保留主体 summary、response plan 和 output verdict。",
                response_plan_metadata={
                    "status": "direct_reply_text",
                    "delivery_kind": "final",
                    "authority_source": "response_contract.response_plan",
                    "reply_authority": "host_pre_runtime",
                    "conversation_act": "direct_reply_text",
                },
            )
        return original_plan_pre_runtime(decision, state)

    bridge.inspect_ingress_semantic = MethodType(fake_semantic, bridge)
    bridge.plan_pre_runtime = MethodType(fake_plan_pre_runtime, bridge)


def _case_profiles() -> Dict[str, Dict[str, Any]]:
    return {
        "你好": {
            "reply_text": "你好，我在。你先把最卡的一步说出来。",
            "reply_mode": "normal",
            "response_tendency_summary": {
                "preferred_mode": "ask",
                "preferred_tone": "supportive",
                "suggested_next_step": "clarify",
                "chat_cadence_mode": "reply_now_normal",
            },
        },
        "我现在有点卡住了，你先帮我理一下": {
            "reply_text": "先别同时推三件事。你先说卡住的是哪一步、你已经试了什么、现在最想得到什么。",
            "reply_mode": "expand",
            "response_tendency_summary": {
                "preferred_mode": "ask",
                "preferred_tone": "steady",
                "suggested_next_step": "isolate_blocker",
                "chat_cadence_mode": "reply_now_expand",
            },
            "integrated_policy_hints": {"selected_priority": "review"},
        },
        "继续": {
            "reply_text": "继续。先做最小闭环，再扩范围。",
            "reply_mode": "short",
            "response_tendency_summary": {
                "preferred_mode": "defer",
                "preferred_tone": "cautious",
                "suggested_next_step": "narrow_scope",
                "chat_cadence_mode": "reply_now_short",
            },
            "initiative_policy_hints": {"initiative_priority": "bounded_continue"},
        },
        "你刚才为什么那样回答": {
            "reply_text": "因为我在优先减少返工。先把问题缩成一个最小可验证动作，比直接扩大动作面更稳。",
            "reply_mode": "normal",
            "response_tendency_summary": {
                "preferred_mode": "explain",
                "preferred_tone": "cautious",
                "suggested_next_step": "justify",
                "chat_cadence_mode": "reply_now_normal",
            },
            "policy_hint": {"delivery_mode": "bounded_explanation"},
        },
        "我先消化一下": {
            "reply_text": "好，你先消化。我先不追问，等你回来再继续。",
            "reply_mode": "hold",
            "chat_cadence_mode": "hold_for_followup",
            "response_tendency_summary": {
                "preferred_mode": "defer",
                "preferred_tone": "supportive",
                "suggested_next_step": "hold",
                "chat_cadence_mode": "hold_for_followup",
            },
            "initiative_policy_hints": {"initiative_priority": "hold"},
            "candidate_actions": [{"kind": "hold_for_followup"}],
        },
    }


def _compact_hold_event(event: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(event, dict) or not event:
        return None
    return {
        "reply_text": event.get("reply_text"),
        "delivery_kind": event.get("delivery_kind"),
        "reply_authority": event.get("reply_authority"),
        "reply_origin": event.get("reply_origin"),
        "authority_source": event.get("authority_source"),
        "chat_cadence_mode": event.get("chat_cadence_mode"),
        "response_tendency_summary": dict(event.get("response_tendency_summary") or {}),
        "outbox_lane": event.get("outbox_lane"),
        "outbox_status": event.get("outbox_status"),
    }


async def _run_telegram_case(
    *,
    bot: TelegramBot,
    bridge: TelegramRuntimeBridge,
    runner: _DeterministicParityRunner,
    subject_gate: _AllowSubjectGate,
    state: RuntimeV2State,
    session_key: str,
    case: ParityCase,
    message_id: int,
) -> Dict[str, Any]:
    request = build_telegram_unified_request(
        session_key=session_key,
        text=case.text,
        chat_id=8420019401,
        user_id=456,
        username="parity",
        message_id=message_id,
        source_kind="telegram_prepared",
        raw_event={
            "message": {
                "message_id": message_id,
                "chat": {"id": 8420019401, "type": "private"},
                "from": {"id": 456, "username": "parity"},
                "text": case.text,
            }
        },
    )
    ingress = await build_unified_ingress(request, state, bridge=bridge, llm_client=None)
    state.ingress_context = dict(ingress.ingress_context or {})
    ingress_gate = subject_gate.process_ingress(
        session_id=session_key,
        turn_id=f"telegram_parity:{message_id}",
        source="telegram_prepared",
        user_input=request.effective_user_input,
        state=state,
        evidence_collector=None,
    )
    if not ingress_gate.ok:
        raise RuntimeError("parity subject gate unexpectedly blocked telegram case")

    pre_runtime = ingress.pre_runtime_action
    if getattr(pre_runtime, "should_return_early", False):
        response_plan_metadata = dict(getattr(pre_runtime, "response_plan_metadata", None) or {})
        prepared = bot._prepare_subject_gated_host_owned_delivery(
            state=state,
            session_id=session_key,
            turn_id=f"telegram_pre_runtime:{message_id}",
            reply_text=getattr(pre_runtime, "direct_reply_text", None) or "",
            status=response_plan_metadata.get("status", "direct_reply_text"),
            delivery_kind=response_plan_metadata.get("delivery_kind", "final"),
            authority_source=response_plan_metadata.get("authority_source", "response_contract.response_plan"),
            reply_authority=response_plan_metadata.get("reply_authority", "host_pre_runtime"),
            metadata=response_plan_metadata,
            channel="telegram",
            source_kind="telegram_prepared",
            transport_meta=build_telegram_transport_meta(
                chat_id=8420019401,
                user_id=456,
                username="parity",
                message_id=message_id,
            ),
        )
        return {
            "snapshot": build_host_contract_snapshot(
                request=request,
                ingress=ingress,
                turn_result=prepared.get("unified_turn"),
                egress=prepared.get("unified_egress"),
            ),
            "hold_event": None,
        }

    result = await runner.run_turn(
        session_key=session_key,
        user_input=request.effective_user_input,
        state=state,
        source="telegram_prepared",
        evidence_collector=None,
    )
    output_verdict, response_plan = await bot._finalize_runtime_delivery_contract(
        session_key=session_key,
        state=state,
        result=result,
        source="telegram_prepared",
        trace_id=f"trace-{message_id}",
        ingress_message_id=message_id,
    )
    unified_turn = build_unified_turn_result(
        state=state,
        runtime_result=result,
        request=request,
        ingress=ingress,
        response_plan=response_plan,
        output_verdict=output_verdict,
        metadata={
            "channel": "telegram",
            "source_kind": "telegram_prepared",
            "runtime_action": (state.ingress_context or {}).get("runtime_action"),
        },
    )
    unified_egress = build_unified_egress(
        unified_turn,
        state,
        bridge=bridge,
        transport_meta=build_telegram_transport_meta(
            chat_id=8420019401,
            user_id=456,
            username="parity",
            message_id=message_id,
        ),
    )
    hold_event = None
    if str(getattr(response_plan, "chat_cadence_mode", "") or "").strip() == "hold_for_followup":
        hold_result = await bot._enqueue_chat_hold_followup(
            session_key=session_key,
            state=state,
            response_plan=response_plan,
            output_verdict=output_verdict,
            trace_id=f"trace-{message_id}",
            ingress_message_id=message_id,
        )
        hold_event = _compact_hold_event((hold_result or {}).get("queued_event"))
    return {
        "snapshot": build_host_contract_snapshot(
            request=request,
            ingress=ingress,
            turn_result=unified_turn,
            egress=unified_egress,
        ),
        "hold_event": hold_event,
    }


def run_unified_host_contract_parity() -> Dict[str, Any]:
    bridge = TelegramRuntimeBridge()
    direct_reply_text = PARITY_WINDOWS["direct_reply_window"][0].text
    _patch_bridge_for_parity(bridge, direct_reply_text=direct_reply_text)
    runner = _DeterministicParityRunner(_case_profiles())
    subject_gate = _AllowSubjectGate()

    dashboard_service = DashboardChatService(
        bridge=bridge,
        runner=runner,
        subject_gate=subject_gate,
        llm_client_resolver=lambda: None,
    )
    telegram_bot = TelegramBot(token="parity-token", use_runtime_v2=True)
    telegram_bot.telegram_runtime_bridge = bridge
    telegram_bot.runtime_v2_bridge = bridge
    telegram_bot.subject_gate = subject_gate
    telegram_bot._get_subject_gate = lambda: subject_gate  # type: ignore[method-assign]

    cases_report: List[Dict[str, Any]] = []
    parity_pass_count = 0
    hold_consistency_pass_count = 0
    hold_case_count = 0

    for window_name, cases in PARITY_WINDOWS.items():
        dashboard_session = dashboard_service.ensure_session(f"parity-{window_name}")
        session_key = dashboard_session.session_id
        telegram_state = RuntimeV2State(session_id=session_key)
        telegram_state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
        for message_id, case in enumerate(cases, start=1):
            dashboard_payload = dashboard_service.send_message(session_key, case.text)
            dashboard_snapshot = dict(dashboard_payload.get("debug", {}).get("host_contract") or {})
            telegram_result = asyncio.run(
                _run_telegram_case(
                    bot=telegram_bot,
                    bridge=bridge,
                    runner=runner,
                    subject_gate=subject_gate,
                    state=telegram_state,
                    session_key=session_key,
                    case=case,
                    message_id=message_id,
                )
            )
            telegram_snapshot = dict(telegram_result.get("snapshot") or {})
            comparison = compare_host_contract_snapshots(dashboard_snapshot, telegram_snapshot)
            if comparison["match"]:
                parity_pass_count += 1
            hold_consistent = None
            if case.expected_mode == "hold_for_followup":
                hold_case_count += 1
                hold_event = dict(telegram_result.get("hold_event") or {})
                hold_consistent = (
                    hold_event.get("chat_cadence_mode") == "hold_for_followup"
                    and hold_event.get("reply_authority") == "model_chat"
                    and hold_event.get("authority_source") == "response_contract.response_plan"
                    and dashboard_snapshot.get("turn", {}).get("chat_cadence_mode") == "hold_for_followup"
                )
                if hold_consistent:
                    hold_consistency_pass_count += 1
            cases_report.append(
                {
                    "window": window_name,
                    "case_id": case.case_id,
                    "text": case.text,
                    "expected_mode": case.expected_mode,
                    "expectation": case.expectation,
                    "parity_match": comparison["match"],
                    "comparison": comparison,
                    "dashboard_snapshot": dashboard_snapshot,
                    "telegram_prepared_snapshot": telegram_snapshot,
                    "telegram_hold_event": telegram_result.get("hold_event"),
                    "hold_consistent": hold_consistent,
                }
            )

    total_cases = len(cases_report)
    verdict = (
        "pass"
        if parity_pass_count == total_cases and hold_consistency_pass_count == hold_case_count
        else "fail"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": "dashboard_local_vs_telegram_prepared_inprocess",
        "claim_ceiling": "host_contract_only",
        "contract_version": "unified_host_contract.v1",
        "aggregate": {
            "total_cases": total_cases,
            "parity_pass_count": parity_pass_count,
            "parity_fail_count": total_cases - parity_pass_count,
            "hold_case_count": hold_case_count,
            "hold_consistency_pass_count": hold_consistency_pass_count,
            "verdict": verdict,
        },
        "cases": cases_report,
    }


__all__ = ["PARITY_WINDOWS", "run_unified_host_contract_parity"]
