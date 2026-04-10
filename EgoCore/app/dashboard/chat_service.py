from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE

from app.config import get_config
from app.llm_client import get_llm_client
from app.openemotion_hooks import MandatorySubjectGate, NativeOpenEmotionHooks, SubjectGateVerdict
from app.response_contract import apply_output_check, build_direct_response_plan, build_runtime_result_response_plan
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.unified_channel_contract import (
    UnifiedIngressBundle,
    UnifiedIngressRequest,
    build_dashboard_unified_request,
    build_unified_egress,
    build_unified_ingress,
    build_unified_turn_result,
)
from app.telegram_runtime_bridge import TelegramPreRuntimeAction, TelegramRuntimeBridge
from app.telegram_runtime_fallback import TelegramRuntimeFallbackRunner
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult
from app.tools import execute_tool

logger = logging.getLogger(__name__)


class DashboardChatError(RuntimeError):
    status_code = 500
    error_code = "dashboard_chat_error"

    def __init__(self, message: str, *, error_code: Optional[str] = None) -> None:
        super().__init__(message)
        if error_code:
            self.error_code = error_code


class DashboardChatValidationError(DashboardChatError):
    status_code = 400
    error_code = "dashboard_chat_validation_error"


class DashboardChatNotFoundError(DashboardChatError):
    status_code = 404
    error_code = "dashboard_chat_not_found"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_text(value: Any, *, limit: int = 280) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _compact_response_plan_metadata(metadata: Optional[dict]) -> dict:
    source = dict(metadata or {})
    compact: dict = {}

    recent_result_context = dict(source.get("recent_result_context") or {})
    if recent_result_context:
        compact["recent_result_context"] = {
            "binding_kind": recent_result_context.get("binding_kind"),
            "source_turn_id": recent_result_context.get("source_turn_id"),
            "runtime_status": recent_result_context.get("runtime_status"),
            "reply_origin": recent_result_context.get("reply_origin"),
            "delivery_kind": recent_result_context.get("delivery_kind"),
            "target_name": recent_result_context.get("target_name"),
            "target_path": recent_result_context.get("target_path"),
            "reply_preview": recent_result_context.get("reply_preview"),
            "tool_result_summary": dict(recent_result_context.get("tool_result_summary") or {}),
        }
    if source.get("result_binding_source_turn"):
        compact["result_binding_source_turn"] = source.get("result_binding_source_turn")
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
    if source.get("final_text_preview"):
        compact["final_text_preview"] = source.get("final_text_preview")
    if source.get("final_text_hash"):
        compact["final_text_hash"] = source.get("final_text_hash")
    if source.get("final_text_length") is not None:
        compact["final_text_length"] = source.get("final_text_length")
    if source.get("memory_claim_reason"):
        compact["memory_claim_reason"] = source.get("memory_claim_reason")
    if source.get("intent_contract_source_status"):
        compact["intent_contract_source_status"] = source.get("intent_contract_source_status")
    return compact


def _compact_ingress_context(ingress_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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


def _compact_proto_self_context(proto_self_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = dict(proto_self_context or {})
    return {
        "available": bool(source),
        "subject_profile": source.get("subject_profile"),
        "policy_hint": dict(source.get("policy_hint") or {}),
        "response_tendency": dict(source.get("response_tendency") or {}),
        "candidate_actions": list(source.get("candidate_actions") or []),
        "governor_hint": dict(source.get("governor_hint") or {}),
        "self_model_writeback": source.get("self_model_writeback"),
        "developmental_writeback": source.get("developmental_writeback"),
        "social_writeback": source.get("social_writeback"),
        "embodied_writeback": source.get("embodied_writeback"),
        "selfhood_integration_writeback": source.get("selfhood_integration_writeback"),
        "initiative_writeback": source.get("initiative_writeback"),
        "initiative_realization_writeback": source.get("initiative_realization_writeback"),
        "finalized_result_present": isinstance(source.get("finalized_result"), dict),
        "external_result_present": isinstance(source.get("external_result"), dict),
    }


def _sanitize_session_name(name: str) -> tuple[str, str]:
    raw_name = str(name or "").strip() or "default"
    slug = re.sub(r"[^0-9A-Za-z._-]+", "_", raw_name).strip("._-").lower()
    if not slug:
        slug = f"session_{hashlib.sha1(raw_name.encode('utf-8')).hexdigest()[:8]}"
    return raw_name[:80], slug[:80]


@dataclass
class DashboardChatSession:
    session_id: str
    session_name: str
    state: RuntimeV2State
    transcript: list[dict[str, Any]] = field(default_factory=list)
    debug_history: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_debug: Optional[dict[str, Any]] = None
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    turn_count: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class DashboardChatService:
    def __init__(
        self,
        *,
        bridge: Optional[TelegramRuntimeBridge] = None,
        runner: Optional[Any] = None,
        subject_gate: Optional[Any] = None,
        llm_client_resolver: Optional[Any] = None,
    ) -> None:
        self.bridge = bridge or TelegramRuntimeBridge()
        self.runner = runner or TelegramRuntimeFallbackRunner()
        self.subject_gate = subject_gate or MandatorySubjectGate(hooks=NativeOpenEmotionHooks())
        self._llm_client_resolver = llm_client_resolver or self._default_semantic_parse_client
        self._sessions: dict[str, DashboardChatSession] = {}
        self._sessions_lock = threading.RLock()
        self.default_session_id = self.ensure_session("default").session_id

    def _default_semantic_parse_client(self) -> Optional[Any]:
        try:
            config = get_config()
            chat_cfg = config.get_llm_config_for_use_case("chat")
            provider = str(chat_cfg.get("provider") or config.llm.get("default_provider") or "").strip() or None
            model = str(chat_cfg.get("model") or config.llm.get("default_model") or "").strip() or None
            if not provider and not model:
                return None
            return get_llm_client(provider=provider, model=model)
        except Exception as exc:
            logger.warning("dashboard_chat.semantic_parse_client_unavailable err=%s", exc)
            return None

    def _build_runtime_state(self, session_id: str) -> RuntimeV2State:
        state = RuntimeV2State(session_id=session_id)
        state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
        return state

    def ensure_session(self, name: str) -> DashboardChatSession:
        session_name, session_slug = _sanitize_session_name(name)
        session_id = f"dashboard:test:{session_slug}"
        with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = DashboardChatSession(
                    session_id=session_id,
                    session_name=session_name,
                    state=self._build_runtime_state(session_id),
                )
                self._sessions[session_id] = session
            else:
                session.session_name = session_name
            session.updated_at = _utc_now_iso()
            return session

    def get_session(self, session_id: str) -> DashboardChatSession:
        with self._sessions_lock:
            session = self._sessions.get(str(session_id or "").strip())
        if session is None:
            raise DashboardChatNotFoundError(f"Unknown session: {session_id}", error_code="unknown_session")
        return session

    def list_sessions(self) -> Dict[str, Any]:
        with self._sessions_lock:
            sessions = sorted(
                self._sessions.values(),
                key=lambda item: (item.updated_at, item.session_id),
                reverse=True,
            )
        return {
            "default_session_id": self.default_session_id,
            "sessions": [self._build_session_descriptor(session) for session in sessions],
        }

    def create_or_select_session(self, *, name: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        if session_id:
            session = self.get_session(session_id)
        else:
            session = self.ensure_session(name or "default")
        return {
            "session": self._build_session_descriptor(session),
            "session_state": self._build_session_state_summary(session.state),
        }

    def get_session_payload(self, session_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        with session.lock:
            return {
                "session": self._build_session_descriptor(session),
                "transcript": list(session.transcript),
                "last_debug": dict(session.last_debug or {}) if session.last_debug else None,
                "debug_history": dict(session.debug_history or {}),
                "session_state": self._build_session_state_summary(session.state),
            }

    def send_message(self, session_id: str, text: str) -> Dict[str, Any]:
        body = str(text or "").strip()
        if not body:
            raise DashboardChatValidationError("Message text is required.", error_code="empty_message")
        session = self.get_session(session_id)
        with session.lock:
            return asyncio.run(self._send_message_async(session=session, text=body))

    async def _send_message_async(self, *, session: DashboardChatSession, text: str) -> Dict[str, Any]:
        session.turn_count += 1
        trace_id = uuid.uuid4().hex[:10]
        user_message = self._append_message(
            session,
            role="user",
            text=text,
            status="received",
            delivery_kind="ingress",
        )
        request = build_dashboard_unified_request(
            session_key=session.session_id,
            session_name=session.session_name,
            text=text,
            message_id=session.turn_count,
            source_kind="dashboard_local",
            raw_event={
                "dashboard_chat": {
                    "session_id": session.session_id,
                    "session_name": session.session_name,
                    "message_id": session.turn_count,
                    "text": text,
                    "source_kind": "dashboard_local",
                    "trace_id": trace_id,
                    "created_at": user_message["created_at"],
                }
            },
        )
        llm_client = self._llm_client_resolver() if callable(self._llm_client_resolver) else None
        unified_ingress = await build_unified_ingress(
            request,
            session.state,
            bridge=self.bridge,
            llm_client=llm_client,
        )
        session.state.ingress_context = dict(unified_ingress.ingress_context or {})
        self._sync_pending_result_continuation_from_ingress(session.state, user_text=request.effective_user_input)
        pre_runtime = unified_ingress.pre_runtime_action
        if getattr(pre_runtime, "remember_challenge_turn", False):
            session.state.last_challenge_turn = request.effective_user_input

        ingress_gate = self.subject_gate.process_ingress(
            session_id=session.session_id,
            turn_id=self._build_subject_turn_id(session, trace_id),
            source="api:dashboard",
            user_input=request.effective_user_input,
            state=session.state,
            evidence_collector=None,
        )
        if not ingress_gate.ok:
            assistant_message = self._append_message(
                session,
                role="assistant",
                text=ingress_gate.reply_text,
                status="subject_gate_blocked",
                delivery_kind="final",
            )
            debug = self._build_debug_payload(
                trace_id=trace_id,
                request=request,
                ingress=unified_ingress,
                ingress_gate=ingress_gate,
                finalize_gate=None,
                response_plan=None,
                output_verdict=None,
                delivery={"should_send": True, "delivery_kind": "final", "text": ingress_gate.reply_text},
                state=session.state,
            )
            self._store_debug(session, assistant_message, debug)
            return self._build_turn_response(session, user_message=user_message, assistant_message=assistant_message, debug=debug)

        if session.state.get_pending_task_conflict() is not None:
            return await self._complete_host_owned_turn(
                session=session,
                request=request,
                ingress=unified_ingress,
                trace_id=trace_id,
                ingress_gate=ingress_gate,
                reply_text=self._build_task_conflict_reply(session.state),
                status="task_conflict_pending",
                delivery_kind="final",
                authority_source="host_pre_runtime",
                reply_authority="host_task_conflict",
                metadata={"conversation_act": "task_conflict"},
                user_message=user_message,
            )

        if pre_runtime.should_return_early:
            return await self._complete_pre_runtime_turn(
                session=session,
                request=request,
                ingress=unified_ingress,
                trace_id=trace_id,
                ingress_gate=ingress_gate,
                pre_runtime=pre_runtime,
                user_message=user_message,
            )

        result = await self.runner.run_turn(
            session_key=session.session_id,
            user_input=request.effective_user_input,
            state=session.state,
            source="api:dashboard",
            evidence_collector=None,
        )
        output_verdict, response_plan = self._finalize_runtime_delivery_contract(session.state, result)
        unified_turn = build_unified_turn_result(
            state=session.state,
            runtime_result=result,
            request=request,
            ingress=unified_ingress,
            response_plan=response_plan,
            output_verdict=output_verdict,
            metadata={
                "channel": request.channel,
                "source_kind": request.source_kind,
                "transport": "dashboard_local",
            },
        )
        unified_egress = build_unified_egress(
            unified_turn,
            session.state,
            bridge=self.bridge,
            transport_meta={"client": "dashboard_local"},
        )
        assistant_message = None
        if unified_egress.should_send and unified_egress.user_visible_text:
            assistant_message = self._append_message(
                session,
                role="assistant",
                text=unified_egress.user_visible_text,
                status=result.status,
                delivery_kind=unified_egress.delivery_kind or result.delivery_kind or "chat",
            )
        debug = self._build_debug_payload(
            trace_id=trace_id,
            request=request,
            ingress=unified_ingress,
            ingress_gate=ingress_gate,
            finalize_gate=None,
            response_plan=response_plan,
            output_verdict=output_verdict,
            delivery={
                "should_send": bool(unified_egress.should_send),
                "delivery_kind": unified_egress.delivery_kind,
                "text": unified_egress.user_visible_text,
            },
            state=session.state,
        )
        self._store_debug(session, assistant_message, debug)
        return self._build_turn_response(session, user_message=user_message, assistant_message=assistant_message, debug=debug)

    async def _complete_pre_runtime_turn(
        self,
        *,
        session: DashboardChatSession,
        request: UnifiedIngressRequest,
        ingress: UnifiedIngressBundle,
        trace_id: str,
        ingress_gate: SubjectGateVerdict,
        pre_runtime: TelegramPreRuntimeAction,
        user_message: Dict[str, Any],
    ) -> Dict[str, Any]:
        if getattr(pre_runtime, "rule_enforcement", None) and pre_runtime.rule_enforcement.get("kind") == "read_only_preflight":
            session.state.task_status = "waiting_input"
            session.state.waiting_for_user_input = True
            waiting_text = await self._build_profile_rule_preflight_reply(session.state, pre_runtime.rule_enforcement)
            response_plan_metadata = dict(getattr(pre_runtime, "response_plan_metadata", None) or {})
            return await self._complete_host_owned_turn(
                session=session,
                request=request,
                ingress=ingress,
                trace_id=trace_id,
                ingress_gate=ingress_gate,
                reply_text=waiting_text,
                status=response_plan_metadata.get("status", "read_only_preflight"),
                delivery_kind=response_plan_metadata.get("delivery_kind", "waiting_input"),
                authority_source=response_plan_metadata.get("authority_source", "response_contract.response_plan"),
                reply_authority=response_plan_metadata.get("reply_authority", "host_pre_runtime"),
                metadata={
                    "conversation_act": "read_only_preflight",
                    "rule_enforcement": dict(getattr(pre_runtime, "rule_enforcement", {}) or {}),
                    "matched_rule_ids": response_plan_metadata.get("matched_rule_ids") or [],
                    "enforcement": response_plan_metadata.get("enforcement"),
                },
                user_message=user_message,
            )

        if getattr(pre_runtime, "force_waiting_input", False):
            session.state.task_status = "waiting_input"
            session.state.waiting_for_user_input = True
            return await self._complete_host_owned_turn(
                session=session,
                request=request,
                ingress=ingress,
                trace_id=trace_id,
                ingress_gate=ingress_gate,
                reply_text=getattr(pre_runtime, "waiting_input_text", None) or "收到内容，请告诉我你要做什么。",
                status="force_waiting_input",
                delivery_kind="final",
                authority_source="response_contract.response_plan",
                reply_authority="host_pre_runtime",
                metadata={"conversation_act": "force_waiting_input"},
                user_message=user_message,
            )

        if getattr(pre_runtime, "direct_reply_text", None):
            response_plan_metadata = dict(getattr(pre_runtime, "response_plan_metadata", None) or {})
            return await self._complete_host_owned_turn(
                session=session,
                request=request,
                ingress=ingress,
                trace_id=trace_id,
                ingress_gate=ingress_gate,
                reply_text=pre_runtime.direct_reply_text,
                status=response_plan_metadata.get("status", "direct_reply_text"),
                delivery_kind=response_plan_metadata.get("delivery_kind", "final"),
                authority_source=response_plan_metadata.get("authority_source", "response_contract.response_plan"),
                reply_authority=response_plan_metadata.get("reply_authority", "host_pre_runtime"),
                metadata={
                    "conversation_act": "direct_reply_text",
                    "matched_rule_ids": response_plan_metadata.get("matched_rule_ids") or [],
                    "enforcement": response_plan_metadata.get("enforcement"),
                },
                user_message=user_message,
            )

        raise DashboardChatValidationError("Unsupported pre-runtime early return.", error_code="unsupported_pre_runtime")

    async def _complete_host_owned_turn(
        self,
        *,
        session: DashboardChatSession,
        request: UnifiedIngressRequest,
        ingress: UnifiedIngressBundle,
        trace_id: str,
        ingress_gate: SubjectGateVerdict,
        reply_text: str,
        status: str,
        delivery_kind: str,
        authority_source: str,
        reply_authority: str,
        metadata: Optional[Dict[str, Any]],
        user_message: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan = build_direct_response_plan(
            reply_text,
            kind=status,
            delivery_kind=delivery_kind,
            authority_source=authority_source,
            reply_authority=reply_authority,
            metadata=dict(metadata or {}),
            state=session.state,
        )
        output_verdict = apply_output_check(plan, session.state)
        if not output_verdict.passed:
            raise DashboardChatValidationError("Host-owned reply produced empty output.", error_code="host_reply_empty")

        turn_result = TelegramTurnResult(
            status=status,
            state=session.state,
            reply=TelegramTurnReply(
                reply_text=output_verdict.reply_text,
                delivery_kind=output_verdict.delivery_kind,
                status=status,
            ),
        )
        finalize_gate = self.subject_gate.finalize_host_owned_result(
            session_id=session.session_id,
            turn_id=f"dashboard_host:{trace_id}",
            result=turn_result,
            state=session.state,
            evidence_collector=None,
        )
        if not finalize_gate.ok:
            assistant_message = self._append_message(
                session,
                role="assistant",
                text=finalize_gate.reply_text,
                status="subject_gate_finalize_blocked",
                delivery_kind="final",
            )
            debug = self._build_debug_payload(
                trace_id=trace_id,
                request=request,
                ingress=ingress,
                ingress_gate=ingress_gate,
                finalize_gate=finalize_gate,
                response_plan=plan,
                output_verdict=output_verdict,
                delivery={"should_send": True, "delivery_kind": "final", "text": finalize_gate.reply_text},
                state=session.state,
            )
            self._store_debug(session, assistant_message, debug)
            return self._build_turn_response(session, user_message=user_message, assistant_message=assistant_message, debug=debug)

        unified_turn = build_unified_turn_result(
            state=session.state,
            runtime_result=turn_result,
            request=request,
            ingress=ingress,
            response_plan=plan,
            output_verdict=output_verdict,
            metadata={
                "channel": request.channel,
                "source_kind": request.source_kind,
                "transport": "dashboard_local",
                "authority_source": authority_source,
                "reply_authority": reply_authority,
            },
        )
        unified_egress = build_unified_egress(
            unified_turn,
            session.state,
            transport_meta={"client": "dashboard_local"},
        )
        assistant_message = self._append_message(
            session,
            role="assistant",
            text=unified_egress.user_visible_text,
            status=status,
            delivery_kind=unified_egress.delivery_kind or delivery_kind,
        )
        debug = self._build_debug_payload(
            trace_id=trace_id,
            request=request,
            ingress=ingress,
            ingress_gate=ingress_gate,
            finalize_gate=finalize_gate,
            response_plan=plan,
            output_verdict=output_verdict,
            delivery={
                "should_send": bool(unified_egress.should_send),
                "delivery_kind": unified_egress.delivery_kind,
                "text": unified_egress.user_visible_text,
            },
            state=session.state,
        )
        self._store_debug(session, assistant_message, debug)
        return self._build_turn_response(session, user_message=user_message, assistant_message=assistant_message, debug=debug)

    async def _build_profile_rule_preflight_reply(self, state: RuntimeV2State, rule_enforcement: dict) -> str:
        target = (state.ingress_context or {}).get("resolved_target") or {}
        target_path = target.get("path") or rule_enforcement.get("target_path")
        summary = rule_enforcement.get("summary") or "这轮受默认高风险流程约束。"
        intro = "按你设定的默认流程，这次我先不直接改文件。"

        if not target_path:
            return (
                f"{intro}\n\n"
                f"只读检查：{summary}\n"
                "最小验证动作：先告诉我具体目标路径或要执行的高风险动作，我再继续。"
            )

        result = await asyncio.to_thread(
            execute_tool,
            "file",
            {"operation": "read", "path": target_path},
            None,
            "dashboard_profile_rule_read_only_preflight",
        )
        result_dict = result.to_dict()
        filename = os.path.basename(target_path.replace("\\", "/")) or target_path

        if result_dict.get("success"):
            content = result_dict.get("output") or ""
            lower = content.lower()
            file_kind = "HTML 文件" if "<html" in lower or "<!doctype html" in lower else "文本文件"
            char_count = len(content)
            return (
                f"{intro}\n\n"
                f"只读检查：已读取 `{filename}`，当前是 {file_kind}（{char_count} 字符）。\n"
                "最小验证动作：先明确这次只改哪 1 个点，或直接回复“继续”让我按默认流程进入正式修改。"
            )

        error = str(result_dict.get("error") or "unknown_error")
        return (
            f"{intro}\n\n"
            f"只读检查：读取 `{filename}` 失败，原因：{error}\n"
            "最小验证动作：先确认目标路径可访问，或给我正确文件路径后我继续。"
        )

    def _sync_pending_result_continuation_from_ingress(self, state: RuntimeV2State, *, user_text: str) -> None:
        ingress_context = dict(getattr(state, "ingress_context", None) or {})
        recent_result_binding = bool(ingress_context.get("recent_result_binding"))
        runtime_action = str(ingress_context.get("runtime_action") or "").strip()
        request_mode = str(ingress_context.get("request_mode") or "").strip() or None
        resolved_target = dict(ingress_context.get("resolved_target") or {})
        pending_existing = dict(getattr(state, "pending_result_continuation", None) or {})
        correction_context = bool(ingress_context.get("correction_context"))

        if recent_result_binding and request_mode in {"analyze", "write"}:
            target_path = str(
                resolved_target.get("path")
                or pending_existing.get("target_path")
                or ((state.recent_delivered_result_context or {}).get("target_path") if isinstance(state.recent_delivered_result_context, dict) else "")
                or ""
            ).strip() or None
            target_name = str(
                resolved_target.get("filename")
                or pending_existing.get("target_name")
                or ((state.recent_delivered_result_context or {}).get("target_name") if isinstance(state.recent_delivered_result_context, dict) else "")
                or ""
            ).strip() or None
            source_turn_id = str(
                pending_existing.get("source_turn_id")
                or ((state.recent_delivered_result_context or {}).get("source_turn_id") if isinstance(state.recent_delivered_result_context, dict) else "")
                or ""
            ).strip() or None
            status = str(pending_existing.get("status") or "").strip() or "pending"
            if correction_context or str(pending_existing.get("requested_mode") or "").strip() != request_mode:
                status = "pending"
            state.set_pending_result_continuation(
                {
                    "target_path": target_path,
                    "target_name": target_name,
                    "source_turn_id": source_turn_id,
                    "requested_mode": request_mode,
                    "status": status,
                    "last_user_request": user_text[:300],
                    "needs_clarification": bool(pending_existing.get("needs_clarification")) if pending_existing else False,
                    "clarification_question": pending_existing.get("clarification_question") if pending_existing else None,
                    "correction_context": correction_context,
                    "bound_to_recent_result": True,
                }
            )
            return

        if runtime_action == "return_runtime_status" and pending_existing:
            state.update_pending_result_continuation(last_user_request=user_text[:300])
            return

        if runtime_action == "execute_task" and not recent_result_binding:
            state.clear_pending_result_continuation()

    def _finalize_pending_result_continuation_after_response(
        self,
        state: RuntimeV2State,
        response_plan: Any,
        result_status: Optional[str],
    ) -> None:
        metadata = dict(getattr(response_plan, "metadata", None) or {})
        pending = dict(getattr(state, "pending_result_continuation", None) or {})
        if not pending:
            return
        if isinstance(metadata.get("recent_result_context"), dict) and metadata.get("recent_result_context"):
            state.clear_pending_result_continuation()
            return
        if str(result_status or "").strip() in {"completed_verified", "completed", "blocked", "failed"}:
            ingress_context = dict(getattr(state, "ingress_context", None) or {})
            if ingress_context.get("recent_result_binding"):
                state.clear_pending_result_continuation()

    def _finalize_runtime_delivery_contract(self, state: RuntimeV2State, result: TelegramTurnResult):
        response_plan = build_runtime_result_response_plan(result, state)
        output_verdict = apply_output_check(response_plan, state)
        if output_verdict.passed:
            if result.reply is None:
                result.reply = TelegramTurnReply(
                    reply_text=output_verdict.reply_text,
                    delivery_kind=output_verdict.delivery_kind,
                    status=result.status,
                )
            else:
                result.reply.reply_text = output_verdict.reply_text
                result.reply.delivery_kind = output_verdict.delivery_kind
        if (
            output_verdict.evidence_snapshot
            and output_verdict.fidelity_mode == "verbatim"
            and output_verdict.fidelity_gap is False
        ):
            state.set_last_delivered_evidence_context(output_verdict.evidence_snapshot)
        else:
            state.clear_last_delivered_evidence_context()
        recent_result_context = dict(getattr(response_plan, "metadata", None) or {}).get("recent_result_context")
        if isinstance(recent_result_context, dict) and recent_result_context:
            state.set_recent_delivered_result_context(recent_result_context)
        self._finalize_pending_result_continuation_after_response(state, response_plan, result.status)
        return output_verdict, response_plan

    def _build_task_conflict_reply(self, state: RuntimeV2State) -> str:
        conflict = state.get_pending_task_conflict()
        if conflict is None:
            return "当前没有待确认的新任务。"
        return (
            "当前已有一个活跃任务。你刚刚又发了一个新的执行任务。\n\n"
            f"新任务：{conflict.incoming_text[:140]}\n\n"
            "用 `/replace` 会结束旧任务并开始新任务；用 `/append` 会把它排到当前任务后面；用 `/cancel` 会保持当前任务不变。"
        )

    def _build_session_descriptor(self, session: DashboardChatSession) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "session_name": session.session_name,
            "message_count": len(session.transcript),
            "turn_count": session.turn_count,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "task_status": session.state.task_status,
            "waiting_for_user_input": bool(session.state.waiting_for_user_input),
        }

    def _build_session_state_summary(self, state: RuntimeV2State) -> Dict[str, Any]:
        return {
            "task_status": state.task_status,
            "active_turn_id": state.active_turn_id,
            "active_turn_status": state.active_turn_status,
            "waiting_for_user_input": bool(state.waiting_for_user_input),
            "current_goal": state.current_goal,
            "current_step": state.current_step,
            "last_delivery_type": state.last_delivery_type,
            "generation_id": state.generation_id,
            "ingress_context": _compact_ingress_context(state.ingress_context),
            "proto_self": _compact_proto_self_context(state.proto_self_context),
            "recent_delivered_result_context": dict(state.recent_delivered_result_context or {}),
            "pending_result_continuation": state.build_pending_result_continuation_summary(),
        }

    def _append_message(
        self,
        session: DashboardChatSession,
        *,
        role: str,
        text: str,
        status: str,
        delivery_kind: str,
    ) -> Dict[str, Any]:
        message = {
            "message_id": f"msg_{len(session.transcript) + 1:05d}",
            "role": role,
            "text": str(text or ""),
            "status": status,
            "delivery_kind": delivery_kind,
            "created_at": _utc_now_iso(),
        }
        session.transcript.append(message)
        session.updated_at = message["created_at"]
        return message

    def _store_debug(
        self,
        session: DashboardChatSession,
        assistant_message: Optional[Dict[str, Any]],
        debug: Dict[str, Any],
    ) -> None:
        session.last_debug = debug
        if assistant_message is not None:
            session.debug_history[assistant_message["message_id"]] = debug
        session.updated_at = _utc_now_iso()

    def _build_turn_response(
        self,
        session: DashboardChatSession,
        *,
        user_message: Dict[str, Any],
        assistant_message: Optional[Dict[str, Any]],
        debug: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "session": self._build_session_descriptor(session),
            "messages": {
                "user": user_message,
                "assistant": assistant_message,
            },
            "debug": debug,
            "session_state": self._build_session_state_summary(session.state),
        }

    def _build_subject_turn_id(self, session: DashboardChatSession, trace_id: str) -> str:
        return f"dashboard_local:{session.session_id}:msg{session.turn_count}:trace-{trace_id}"

    def _build_debug_payload(
        self,
        *,
        trace_id: str,
        request: UnifiedIngressRequest,
        ingress: UnifiedIngressBundle,
        ingress_gate: SubjectGateVerdict,
        finalize_gate: Optional[SubjectGateVerdict],
        response_plan: Optional[Any],
        output_verdict: Optional[Any],
        delivery: Dict[str, Any],
        state: RuntimeV2State,
    ) -> Dict[str, Any]:
        ingress_context = dict(ingress.ingress_context or {})
        decision = ingress.semantic_decision
        response_metadata = getattr(response_plan, "metadata", None) if response_plan is not None else None
        return {
            "trace_id": trace_id,
            "request": {
                "channel": request.channel,
                "source_kind": request.source_kind,
                "session_key": request.session_key,
                "user_input": request.user_input,
                "effective_user_input": request.effective_user_input,
                "transport_meta": dict(request.transport_meta or {}),
            },
            "subject_gate": {
                "ingress": {
                    "ok": ingress_gate.ok,
                    "stage": ingress_gate.stage,
                    "reason": ingress_gate.reason,
                    "reply_text": ingress_gate.reply_text,
                    "authority_source": ingress_gate.authority_source,
                },
                "finalize": None
                if finalize_gate is None
                else {
                    "ok": finalize_gate.ok,
                    "stage": finalize_gate.stage,
                    "reason": finalize_gate.reason,
                    "reply_text": finalize_gate.reply_text,
                    "authority_source": finalize_gate.authority_source,
                },
            },
            "ingress": {
                "runtime_action": getattr(decision, "_runtime_action", None),
                "interaction_kind": ingress_context.get("interaction_kind"),
                "request_mode": ingress_context.get("request_mode"),
                "conversation_act": ingress_context.get("conversation_act"),
                "parser_source": ingress_context.get("parser_source"),
                "primary_intent": ingress_context.get("primary_intent"),
                "recent_result_binding": bool(ingress_context.get("recent_result_binding")),
                "correction_context": bool(ingress_context.get("correction_context")),
                "resolved_target": dict(ingress_context.get("resolved_target") or {}),
                "requested_output": dict(ingress_context.get("requested_output") or {}),
                "normalized_turn": ingress.normalized_turn,
                "pre_runtime": {
                    "should_return_early": bool(getattr(ingress.pre_runtime_action, "should_return_early", False)),
                    "force_waiting_input": bool(getattr(ingress.pre_runtime_action, "force_waiting_input", False)),
                    "direct_reply_text": _trim_text(getattr(ingress.pre_runtime_action, "direct_reply_text", None)),
                    "waiting_input_text": _trim_text(getattr(ingress.pre_runtime_action, "waiting_input_text", None)),
                    "rule_enforcement": dict(getattr(ingress.pre_runtime_action, "rule_enforcement", None) or {}),
                },
            },
            "proto_self": _compact_proto_self_context(state.proto_self_context),
            "response_plan": None
            if response_plan is None
            else {
                "kind": getattr(response_plan, "kind", None),
                "delivery_kind": getattr(response_plan, "delivery_kind", None),
                "authority_source": getattr(response_plan, "authority_source", None),
                "reply_authority": getattr(response_plan, "reply_authority", None),
                "chat_cadence_mode": getattr(response_plan, "chat_cadence_mode", None),
                "reply_text_preview": _trim_text(getattr(response_plan, "reply_text", None)),
                "metadata": _compact_response_plan_metadata(response_metadata),
            },
            "output_check": None
            if output_verdict is None
            else {
                "passed": bool(getattr(output_verdict, "passed", False)),
                "reason": getattr(output_verdict, "reason", None),
                "delivery_kind": getattr(output_verdict, "delivery_kind", None),
                "applied_authority": getattr(output_verdict, "applied_authority", None),
                "reply_origin": getattr(output_verdict, "reply_origin", None),
                "intent_gate_status": getattr(output_verdict, "intent_gate_status", None),
                "intent_gate_reason": getattr(output_verdict, "intent_gate_reason", None),
                "reply_text_preview": _trim_text(getattr(output_verdict, "reply_text", None)),
            },
            "delivery": {
                "should_send": bool(delivery.get("should_send")),
                "delivery_kind": delivery.get("delivery_kind"),
                "text_preview": _trim_text(delivery.get("text"), limit=400),
            },
            "session_state": self._build_session_state_summary(state),
        }


__all__ = [
    "DashboardChatError",
    "DashboardChatNotFoundError",
    "DashboardChatService",
    "DashboardChatValidationError",
]
