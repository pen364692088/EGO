"""
OpenEmotion Agent Runtime - Telegram Bot

Handles Telegram bot integration using python-telegram-bot library.
Provides message receiving, command routing, and reply sending.

v2.0.0 (2026-03-19):
- 使用 runEmbeddedEgoCoreAgent 作为唯一入口
- 所有消息走 Session/Lane 串行化
- Reply 通过 ReplyDispatcher 分发
"""

import sys

import asyncio
import hashlib
import logging
import os
import re
import socket
import uuid
from typing import Any, Optional
import json
import time
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from pathlib import Path

from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE
from telegram import BotCommand, Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from app.config import get_config, ConfigError
from app.command_router import (
    get_router, CommandContext, CommandResult, handle_natural_language
)
# v2.0: 新 runtime 入口
from app.runtime import (
    run_agent,
    create_run_id,
    get_session_manager,
    set_telegram_bot,
    DeliveryIdentity,
    DeliveryDedupePolicy,
)
from app.interaction.normalize_user_turn import normalize_user_turn
from app.interaction.session_context_store import get_session_context_store

# E4 Evidence Collector - for capturing outbox_record
try:
    from app.telegram_evidence_collector import get_evidence_collector
    _EVIDENCE_COLLECTOR_AVAILABLE = True
except ImportError:
    _EVIDENCE_COLLECTOR_AVAILABLE = False
try:
    from app.openemotion_adapter.developmental_writeback import (
        record_developmental_projection_from_finalized_sample,
    )
    _DEVELOPMENTAL_WRITEBACK_AVAILABLE = True
except ImportError:
    _DEVELOPMENTAL_WRITEBACK_AVAILABLE = False

from app.runtime_v2 import (
    RuntimeV2FallbackRunner,
    RuntimeV2PromptFiles,
    RuntimeV2State,
    build_telegram_unified_request,
    build_unified_egress,
    build_unified_ingress,
    build_unified_turn_result,
)
from app.runtime_v2.run_items import (
    RunConflictState,
    RunEvent,
    RunItem,
    build_output_obligations,
    build_run_item_started_text,
    build_run_item_verified_text,
    build_run_items_from_request,
)
from app.runtime_v2.progress_events import ProgressEvent, is_terminal_event
from app.runtime_v2.proactive_telegram_cycle import run_host_governed_proactive_cycle
from app.runtime_v2.proactive_outbox import enqueue_controlled_proactive_outbox
from app.runtime_v2.proactive_telegram_policy import (
    ProactiveTelegramEnablePolicy,
    evaluate_proactive_telegram_enable_policy,
)
from app.autonomy import (
    AutonomyExecutorKind,
    AutonomyOrchestrator,
    AutonomyRun,
    AutonomyRunStatus,
    AutonomySliceOutcome,
    AutonomyStopReason,
)
from app.core_bus import BusEvent, get_message_bus, get_session_worker_pool
from app.session_store import SessionLogManager
from app.agent_core import NativeToolCallingLoop
from app.openemotion_hooks import MandatorySubjectGate, NativeOpenEmotionHooks
from app.telegram_runtime_fallback import TelegramRuntimeFallbackRunner
from app.telegram_runtime_bridge import TelegramRuntimeBridge
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult
from app.tools import execute_tool
from app.tools.delivery_bridge import build_tool_delivery_bridge_decision
from app.ingestion.artifact_store import get_artifact_store
from app.compaction import ReadRequest, get_compaction_manager
from app.response_contract import (
    apply_output_check,
    build_direct_response_plan,
    build_runtime_result_response_plan,
    build_status_response_plan,
)
from app.llm_client import get_llm_client
from app.restore_runtime import PendingRestoreObservation

# Ingestion Layer
from app.ingestion import (
    get_ingestion_manager,
    IngestionManager,
    IngestedInput,
)
from app.ingestion.manager import TelegramDocumentInfo

# EgoCore Metrics Integration (Phase: PRODUCTION_INTEGRATION)
# Feature Flag: runtime_metrics_enabled (default: OFF)
# Protection: fast_disable / rollback / timeout / circuit_breaker / exception isolation
try:
    from system_core import record_metric
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

logger = logging.getLogger(__name__)
EXPLICIT_OUTPUT_FILENAME_RE = re.compile(r"(?<![A-Za-z0-9_.\\/\\-])([A-Za-z0-9][A-Za-z0-9 _.-]{0,120}\.[A-Za-z0-9]{1,8})")
TELEGRAM_TEXT_CHUNK_LIMIT = 3500
RECENT_EVIDENCE_RESULT_TTL_SECONDS = 600
READ_LIST_FOLLOWUP_PROBE_KEYS = {
    "空的吗",
    "什么意思空的吗",
    "没看到",
    "你没列出来",
}


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.environ.get(name, "")).strip().lower()
    if not value:
        return bool(default)
    return value in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    value = str(os.environ.get(name, "")).strip()
    if not value:
        return tuple(item for item in default if str(item).strip())
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _env_int_set(name: str) -> Optional[set[int]]:
    values = _env_csv(name, ())
    if not values:
        return None
    parsed: set[int] = set()
    for value in values:
        try:
            parsed.add(int(value))
        except (TypeError, ValueError):
            continue
    return parsed or None


def _env_float(name: str, default: float) -> float:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def _extract_directory_listing_entries(body: str) -> list[str]:
    entries: list[str] = []
    for raw_line in str(body or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("volume in drive"):
            continue
        if lower.startswith("volume serial number"):
            continue
        if lower.startswith("directory of"):
            continue
        if lower.startswith("total files listed"):
            continue
        if " file(s) " in lower and " bytes" in lower:
            continue
        if " dir(s) " in lower and " bytes free" in lower:
            continue
        if "<dir>" in lower:
            name = line.split("<DIR>")[-1].strip()
            if name and name not in {".", ".."}:
                entries.append(name)
            continue
        parts = [part for part in re.split(r"\s{2,}", line) if part]
        if len(parts) >= 2:
            candidate = parts[-1].strip()
            if candidate:
                entries.append(candidate)
            continue
        entries.append(line)
    return entries


class TelegramBot:
    """
    Telegram bot for OpenEmotion Agent Runtime.

    Features:
    - Polling-based message receiving
    - Command routing via CommandRouter
    - Natural language message handling
    - Configurable allowed chat IDs

    v2.0:
    - 使用 runEmbeddedEgoCoreAgent 作为唯一入口
    - Session/Lane 串行化
    - ReplyDispatcher 分发
    """

    def __init__(
        self,
        token: str,
        allowed_chat_ids: Optional[list[int]] = None,
        use_new_runtime: bool = True,
        use_runtime_v2: bool = False,
        pending_restore_observation: Optional[PendingRestoreObservation] = None,
    ):
        """
        Initialize Telegram bot.

        Args:
            token: Telegram bot token
            allowed_chat_ids: Optional list of allowed chat IDs (None = allow all)
            use_new_runtime: compatibility-only path; no longer formal mainline
            use_runtime_v2: formal Telegram mainline path
        """
        self.token = token
        self.allowed_chat_ids = set(allowed_chat_ids) if allowed_chat_ids else None
        self.app: Optional[Application] = None
        self.router = get_router()
        self.use_new_runtime = use_new_runtime
        self.use_runtime_v2 = use_runtime_v2
        self._legacy_runtime_notice_logged = False
        self.telegram_runtime_fallback_runner = TelegramRuntimeFallbackRunner() if use_runtime_v2 else None
        self.runtime_v2_loop = None
        self.runtime_v2_fallback_runner = self.telegram_runtime_fallback_runner
        self.telegram_runtime_bridge = TelegramRuntimeBridge() if use_runtime_v2 else None
        self.runtime_v2_bridge = self.telegram_runtime_bridge
        self.native_loop = None
        self.native_openemotion_hooks = None
        self.subject_gate = None
        self._setup_complete = False
        self._run_started = False
        # Stale reply suppression: remember latest ingress message per session.
        self._latest_message_id_by_session: dict[str, int] = {}
        self._chat_id_by_session: dict[str, int] = {}
        self._mvp12_proactive_telegram_autodrain_enabled = _env_flag(
            "EGO_ENABLE_MVP12_PROACTIVE_TELEGRAM_AUTODRAIN",
            False,
        )
        self._mvp12_proactive_telegram_tick_seconds = _env_float(
            "EGO_MVP12_PROACTIVE_TELEGRAM_TICK_SECONDS",
            30.0,
        )
        self._mvp12_proactive_scheduler_idle_seconds = _env_float(
            "EGO_MVP12_PROACTIVE_SCHEDULER_IDLE_SECONDS",
            600.0,
        )
        self._mvp12_proactive_transport_idle_seconds = _env_float(
            "EGO_MVP12_PROACTIVE_TRANSPORT_IDLE_SECONDS",
            900.0,
        )
        self._mvp12_proactive_reply_cooldown_seconds = _env_float(
            "EGO_MVP12_PROACTIVE_REPLY_COOLDOWN_SECONDS",
            900.0,
        )
        self._mvp12_proactive_allowed_chat_ids = _env_int_set("EGO_MVP12_PROACTIVE_ALLOWED_CHAT_IDS")
        if self._mvp12_proactive_allowed_chat_ids is None and self.allowed_chat_ids is not None:
            self._mvp12_proactive_allowed_chat_ids = set(self.allowed_chat_ids)
        self._mvp12_proactive_allowed_session_prefixes = _env_csv(
            "EGO_MVP12_PROACTIVE_ALLOWED_SESSION_PREFIXES",
            ("telegram:dm:",),
        )
        self._mvp12_proactive_min_recent_user_turns = max(
            1,
            _env_int("EGO_MVP12_PROACTIVE_MIN_RECENT_USER_TURNS", 2),
        )
        self._mvp12_proactive_min_recent_assistant_replies = max(
            1,
            _env_int("EGO_MVP12_PROACTIVE_MIN_RECENT_ASSISTANT_REPLIES", 1),
        )
        self._mvp12_proactive_max_events_per_tick = max(
            1,
            _env_int("EGO_MVP12_PROACTIVE_MAX_EVENTS_PER_TICK", 1),
        )
        self._proactive_telegram_autodrain_task: Optional[asyncio.Task] = None
        self._delivery_dedupe_policy = DeliveryDedupePolicy()
        self._message_bus = get_message_bus()
        self._session_worker_pool = get_session_worker_pool()
        self._session_log_manager = SessionLogManager()
        self._phase1_bus_ready = False
        self._runtime_states: dict[str, RuntimeV2State] = {}
        self._semantic_parse_client: Optional[Any] = None
        self._manual_resume_tasks: dict[str, asyncio.Task] = {}
        self.autonomy_orchestrator = AutonomyOrchestrator() if use_runtime_v2 else None
        self.autonomy_transient_retry_limit = 3
        self.autonomy_rate_limited_retry_limit = 5
        self.autonomy_no_progress_retry_limit = 3
        # Ingestion Manager
        self._ingestion_manager: Optional[IngestionManager] = None
        self._pending_restore_observation = pending_restore_observation
        if self.autonomy_orchestrator is not None:
            self.autonomy_orchestrator.register_surface("telegram", self._resume_telegram_autonomy_run)

    def _hydrate_artifact_ingress_context(self, state: RuntimeV2State) -> dict:
        ingress_context = deepcopy(state.ingress_context or {})
        target = ingress_context.get("resolved_target") or {}
        artifact_id = target.get("artifact_id") or target.get("artifact_ref")
        if not artifact_id or not str(artifact_id).startswith("artifact://"):
            return ingress_context
        ingress_context["resolved_artifact_id"] = str(artifact_id)
        ingress_context["resolved_artifact_filename"] = target.get("filename")
        return ingress_context

    def _build_native_failure_reply(self, state: RuntimeV2State) -> str:
        tool_result = state.last_tool_result or {}
        error = str(tool_result.get("stderr") or tool_result.get("raw", {}).get("error") or "").strip()
        target = (state.ingress_context or {}).get("resolved_target") or {}
        artifact_name = target.get("filename") or "任务内容"
        if not error:
            return "执行时遇到问题，我已经停止继续尝试。请让我改用更直接的方式继续。"
        return (
            f"执行「{artifact_name}」时遇到问题，我已经停止继续尝试。\n\n"
            f"错误：{error}\n\n"
            "如果你愿意，我可以基于这份任务内容直接继续执行，并在出错时立即汇报。"
        )

    def _is_artifact_execute_turn(self, state: RuntimeV2State, ingress=None) -> bool:
        ingress_context = state.ingress_context or {}
        runtime_action = getattr(ingress, "_runtime_action", None) or ingress_context.get("runtime_action")
        if runtime_action != "execute_task":
            return False
        target = ingress_context.get("resolved_target") or {}
        artifact_id = target.get("artifact_id") or target.get("artifact_ref")
        return bool(str(artifact_id).startswith("artifact://"))

    def _should_bypass_task_conflict_for_pending_artifact_execute(self, state: RuntimeV2State, ingress=None) -> bool:
        if not self._is_artifact_execute_turn(state, ingress):
            return False
        ingress_context = state.ingress_context or {}
        target = ingress_context.get("resolved_target") or {}
        target_source = str(target.get("source") or "").strip()
        if getattr(ingress, "is_confirm_execution", False):
            return True
        if state.waiting_for_user_input and getattr(state, "last_inferred_action", None) == "execute":
            return True
        if target_source in {"latest_task_artifact", "last_uploaded_task", "last_uploaded"}:
            return not bool(state.current_goal or state.run_items)
        return False

    def _has_explicit_path_target(self, state: RuntimeV2State) -> bool:
        target = (state.ingress_context or {}).get("resolved_target") or {}
        return bool(target.get("path")) and target.get("source") == "explicit_path"

    def _should_override_stale_task_with_explicit_target(self, state: RuntimeV2State, ingress) -> bool:
        ingress_context = state.ingress_context or {}
        runtime_action = getattr(ingress, "_runtime_action", None) or ingress_context.get("runtime_action")
        if runtime_action != "execute_task" or not self._has_explicit_path_target(state):
            return False
        return bool(
            state.last_uploaded_artifact
            and (
                state.task_status in {"running", "waiting_input", "resumable_pause"}
                or state.waiting_for_user_input
                or state.contract_phase in {"step_selected", "planning_stalled", "re_lock_needed", "executing"}
            )
        )

    def _extract_output_obligations(self, text: str, state: RuntimeV2State) -> list[dict]:
        run_items = self._build_run_items_for_request(text, state)
        return build_output_obligations(run_items) if run_items else []

    def _build_run_items_for_request(self, text: str, state: RuntimeV2State) -> list[RunItem]:
        ingress_context = state.ingress_context or {}
        if ingress_context.get("runtime_action") != "execute_task":
            return []
        return build_run_items_from_request(
            text,
            ingress_context=ingress_context,
            last_explicit_target=state.last_explicit_target,
        )

    def _capture_pre_runtime_response_plan(self, plan, verdict) -> None:
        if not _EVIDENCE_COLLECTOR_AVAILABLE:
            return
        metadata = dict(getattr(plan, "metadata", None) or {})
        try:
            collector = get_evidence_collector()
            collector.capture_host_response_plan(
                status=metadata.get("status", getattr(plan, "kind", "pre_runtime")),
                delivery_kind=getattr(verdict, "delivery_kind", getattr(plan, "delivery_kind", "final")),
                reply_text=getattr(verdict, "reply_text", getattr(plan, "reply_text", "")),
                extra={
                    "authority_source": metadata.get("authority_source", getattr(plan, "authority_source", "host_pre_runtime")),
                    "reply_authority": getattr(plan, "reply_authority", metadata.get("reply_authority", "host_degraded_fallback")),
                    "speaker_mode": getattr(plan, "speaker_mode", None),
                    "epistemic_status": getattr(plan, "epistemic_status", None),
                    "commitment_level": getattr(plan, "commitment_level", None),
                    "must_include": list(getattr(plan, "must_include", ()) or ()),
                    "must_not_upgrade": dict(getattr(plan, "must_not_upgrade", {}) or {}),
                    "tone_bounds": dict(getattr(plan, "tone_bounds", {}) or {}),
                    "memory_claim_reason": metadata.get("memory_claim_reason"),
                    "memory_claim_allowed": metadata.get("memory_claim_allowed"),
                    "memory_claim_detected": metadata.get("memory_claim_detected"),
                    "matched_rule_ids": metadata.get("matched_rule_ids") or [],
                    "rule_enforcement": metadata.get("enforcement"),
                    "output_check_reason": getattr(verdict, "reason", None),
                    "applied_authority": getattr(verdict, "applied_authority", None),
                    "used_host_fallback": getattr(verdict, "used_host_fallback", False),
                    "intent_gate_status": getattr(verdict, "intent_gate_status", None),
                    "intent_gate_reason": getattr(verdict, "intent_gate_reason", None),
                    "intent_gate_would_block": getattr(verdict, "intent_gate_would_block", None),
                    "intent_gate_violation_class": getattr(verdict, "intent_gate_violation_class", None),
                    "intent_gate_violation_types": list(getattr(verdict, "intent_gate_violation_types", ()) or ()),
                    "intent_gate_confidence": getattr(verdict, "intent_gate_confidence", None),
                    "metadata": self._build_compact_response_plan_metadata(metadata),
                },
            )
        except Exception as e:
            logger.warning(f"[E4-EVIDENCE] Failed to capture pre-runtime response_plan: {e}")

    def _build_compact_response_plan_metadata(self, metadata: Optional[dict]) -> dict:
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
        return compact

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

    def _mark_pending_result_continuation_running_if_needed(self, state: RuntimeV2State) -> None:
        pending = dict(getattr(state, "pending_result_continuation", None) or {})
        ingress_context = dict(getattr(state, "ingress_context", None) or {})
        if not pending or not ingress_context.get("recent_result_binding"):
            return
        request_mode = str(ingress_context.get("request_mode") or pending.get("requested_mode") or "").strip()
        if request_mode not in {"analyze", "write"}:
            return
        state.update_pending_result_continuation(
            requested_mode=request_mode,
            status="running",
            correction_context=bool(ingress_context.get("correction_context")),
        )

    def _finalize_pending_result_continuation_after_response(self, state: RuntimeV2State, response_plan: Any, result_status: Optional[str]) -> None:
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

    def _build_pre_runtime_response_plan(self, reply_text: str, pre_runtime, state: RuntimeV2State):
        metadata = getattr(pre_runtime, "response_plan_metadata", None) or {}
        return build_direct_response_plan(
            reply_text,
            kind=metadata.get("status", "pre_runtime"),
            delivery_kind=metadata.get("delivery_kind", "final"),
            authority_source=metadata.get("authority_source", "host_pre_runtime"),
            reply_authority=metadata.get("reply_authority", "host_degraded_fallback"),
            metadata=metadata,
            state=state,
        )

    async def _send_host_owned_reply(
        self,
        update: Update,
        *,
        state: RuntimeV2State,
        reply_text: str,
        status: str,
        delivery_kind: str = "final",
        authority_source: str = "host_pre_runtime",
        reply_authority: str = "host_response_contract",
        metadata: Optional[dict[str, Any]] = None,
        use_markdown: bool = False,
        finalize_evidence: bool = True,
    ) -> bool:
        plan_metadata = {"status": status}
        if metadata:
            plan_metadata.update(metadata)
        plan = build_direct_response_plan(
            reply_text,
            kind=status,
            delivery_kind=delivery_kind,
            authority_source=authority_source,
            reply_authority=reply_authority,
            metadata=plan_metadata,
            state=state,
        )
        verdict = apply_output_check(plan, state)
        if not verdict.passed:
            return False
        session_id = str(
            getattr(state, "session_id", None)
            or f"telegram:chat:{getattr(getattr(update, 'effective_chat', None), 'id', 'unknown')}"
        )
        turn_suffix = (
            str(getattr(getattr(update, "message", None), "message_id", "")).strip()
            or uuid.uuid4().hex[:8]
        )
        turn_result = TelegramTurnResult(
            status=status,
            state=state,
            reply=TelegramTurnReply(
                reply_text=verdict.reply_text,
                delivery_kind=delivery_kind,
                status=status,
            ),
        )
        subject_gate = self._get_subject_gate()
        if subject_gate is not None:
            gate_verdict = subject_gate.finalize_host_owned_result(
                session_id=session_id,
                turn_id=f"host_owned_{turn_suffix}",
                result=turn_result,
                state=state,
                evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
            )
            if not gate_verdict.ok:
                await self._send_reply(
                    update,
                    gate_verdict.reply_text,
                    use_markdown=False,
                    finalize_evidence=finalize_evidence,
                )
                return False
        self._capture_pre_runtime_response_plan(plan, verdict)
        await self._send_reply(
            update,
            verdict.reply_text,
            use_markdown=use_markdown,
            finalize_evidence=finalize_evidence,
        )
        return True

    def _activate_pending_restore_observation(self, state: RuntimeV2State) -> Optional[dict]:
        if self._pending_restore_observation is None:
            return None

        payload = self._pending_restore_observation.to_dict()
        state.ingress_context = state.ingress_context or {}
        state.ingress_context["restore_observation"] = payload

        if _EVIDENCE_COLLECTOR_AVAILABLE:
            try:
                collector = get_evidence_collector()
                collector.capture_restore_observation(payload)
            except Exception as e:
                logger.warning(f"[E4-EVIDENCE] Failed to capture restore observation: {e}")

        self._pending_restore_observation = None
        logger.info(
            "restore.pending_observation_activated restore_id=%s status=%s",
            payload.get("restore_id"),
            payload.get("restore_status"),
        )
        return payload

    async def _publish_tool_delivery_bridge_event(
        self,
        *,
        session_key: str,
        tool_result: Optional[dict],
        reply_text: str,
        delivery_kind: Optional[str],
        source: str,
        applied_authority: Optional[str] = None,
        fidelity_mode: Optional[str] = None,
        fidelity_gap: Optional[bool] = None,
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
    ) -> None:
        decision = build_tool_delivery_bridge_decision(
            tool_result,
            reply_text=reply_text,
            delivery_kind=delivery_kind,
            source=source,
            applied_authority=applied_authority,
            fidelity_mode=fidelity_mode,
            fidelity_gap=fidelity_gap,
        )
        if decision is None:
            return
        await self._publish_phase1_event(
            session_key=session_key,
            kind="tool_delivery_bridge",
            trace_id=trace_id,
            message_id=ingress_message_id,
            payload=decision.to_dict(),
        )

    async def _finalize_runtime_delivery_contract(
        self,
        *,
        session_key: str,
        state: RuntimeV2State,
        result: TelegramTurnResult,
        source: str,
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
    ):
        response_plan = build_runtime_result_response_plan(result, state)
        output_verdict = apply_output_check(response_plan, state)
        if _EVIDENCE_COLLECTOR_AVAILABLE:
            try:
                collector = get_evidence_collector()
                collector.capture_host_response_plan(
                    status=result.status,
                    delivery_kind=output_verdict.delivery_kind,
                    reply_text=output_verdict.reply_text,
                    extra={
                        "authority_source": response_plan.authority_source,
                        "reply_authority": response_plan.reply_authority,
                        "chat_cadence_mode": getattr(response_plan, "chat_cadence_mode", None),
                        "reply_origin": output_verdict.reply_origin,
                        "speaker_mode": response_plan.speaker_mode,
                        "epistemic_status": response_plan.epistemic_status,
                        "commitment_level": response_plan.commitment_level,
                        "must_include": list(response_plan.must_include),
                        "must_not_upgrade": dict(response_plan.must_not_upgrade or {}),
                        "tone_bounds": dict(response_plan.tone_bounds or {}),
                        "memory_claim_reason": (response_plan.memory_claim_verdict.reason if response_plan.memory_claim_verdict else None),
                        "memory_claim_allowed": (response_plan.memory_claim_verdict.allowed if response_plan.memory_claim_verdict else None),
                        "memory_claim_detected": (response_plan.memory_claim_verdict.claim_detected if response_plan.memory_claim_verdict else False),
                        "output_check_reason": output_verdict.reason,
                        "applied_authority": output_verdict.applied_authority,
                        "intent_gate_status": output_verdict.intent_gate_status,
                        "intent_gate_reason": output_verdict.intent_gate_reason,
                        "intent_gate_would_block": output_verdict.intent_gate_would_block,
                        "intent_gate_violation_class": output_verdict.intent_gate_violation_class,
                        "intent_gate_violation_types": list(output_verdict.intent_gate_violation_types),
                        "intent_gate_confidence": output_verdict.intent_gate_confidence,
                        "metadata": self._build_compact_response_plan_metadata(
                            getattr(response_plan, "metadata", None)
                        ),
                    },
                )
            except Exception as e:
                logger.warning(f"[E4-EVIDENCE] Failed to capture runtime response_plan: {e}")
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
        await self._publish_tool_delivery_bridge_event(
            session_key=session_key,
            tool_result=state.last_tool_result,
            reply_text=result.reply_text,
            delivery_kind=result.delivery_kind,
            source=source,
            applied_authority=output_verdict.applied_authority,
            fidelity_mode=output_verdict.fidelity_mode,
            fidelity_gap=output_verdict.fidelity_gap,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
        )
        return output_verdict, response_plan

    def _looks_like_explicit_chat_question(self, state: RuntimeV2State, update: Update) -> bool:
        text = str(getattr(getattr(update, "message", None), "text", None) or state.last_user_turn or "").strip()
        if not text:
            return False
        if "?" in text or "？" in text:
            return True
        lowered = text.lower()
        question_markers = (
            "什么",
            "为什么",
            "怎么",
            "如何",
            "吗",
            "么",
            "是不是",
            "能不能",
            "可不可以",
            "要不要",
            "该不该",
            "行吗",
            "好吗",
            "what",
            "why",
            "how",
            "should i",
            "can you",
            "could you",
        )
        return any(marker in lowered for marker in question_markers)

    def _chat_hold_for_followup_allowed(
        self,
        *,
        session_key: str,
        state: RuntimeV2State,
        update: Update,
        result: TelegramTurnResult,
        response_plan,
        output_verdict,
    ) -> tuple[bool, str]:
        if str(getattr(response_plan, "chat_cadence_mode", "") or "").strip() != "hold_for_followup":
            return False, "cadence_not_hold"
        if result.status != "chat" or not bool(output_verdict.passed) or not str(output_verdict.reply_text or "").strip():
            return False, "result_not_holdable"
        if str(getattr(output_verdict, "applied_authority", "") or "").strip() != "model_chat":
            return False, "authority_not_model_chat"
        metadata = dict(getattr(response_plan, "metadata", None) or {})
        conversation_act = str(metadata.get("conversation_act") or "").strip()
        if conversation_act != "light_chitchat":
            return False, "conversation_act_blocked"
        if self._looks_like_explicit_chat_question(state, update):
            return False, "explicit_question_blocked"
        if str((state.ingress_context or {}).get("runtime_action") or "").strip() not in {"", "chat"}:
            return False, "runtime_action_blocked"

        resolved_chat_id = self._resolve_proactive_chat_id(session_key)
        enable_policy_verdict = evaluate_proactive_telegram_enable_policy(
            session_id=session_key,
            state=state,
            chat_id=resolved_chat_id,
            policy=self._build_proactive_telegram_enable_policy(),
        )
        if not enable_policy_verdict.allowed:
            return False, f"enable_policy:{enable_policy_verdict.reason}"
        return True, "ok"

    async def _enqueue_chat_hold_followup(
        self,
        *,
        session_key: str,
        state: RuntimeV2State,
        response_plan,
        output_verdict,
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> dict[str, Any]:
        metadata = dict(getattr(response_plan, "metadata", None) or {})
        turn_ref = str(getattr(state, "active_turn_id", "") or "").strip() or str(ingress_message_id or uuid.uuid4().hex[:8])
        emitted_delivery = {
            "schema_version": "mvp12.controlled_delivery_record.v1",
            "delivery_status": "artifact_emitted",
            "reply_text": output_verdict.reply_text,
            "text_length": len(str(output_verdict.reply_text or "")),
            "delivery_kind": "chat",
            "reply_authority": output_verdict.applied_authority,
            "reply_origin": output_verdict.reply_origin,
            "authority_source": response_plan.authority_source,
            "chat_cadence_mode": getattr(response_plan, "chat_cadence_mode", None),
            "chat_expression_hint": dict(metadata.get("chat_expression_hint") or {}),
            "response_tendency_summary": dict(metadata.get("response_tendency_summary") or {}),
            "transport_source": "chat_mainline_hold",
            "initiative_mode": "host_governed_chat_hold_followup",
            "initiative_candidate_id": f"chat-hold:{session_key}:{turn_ref}",
            "initiative_source_cycle": turn_ref,
        }
        outbox_result = enqueue_controlled_proactive_outbox(
            session_id=session_key,
            state=state,
            emitted_delivery=emitted_delivery,
            outbox_lane="host_proactive_outbox",
        )
        if hasattr(state, "record"):
            state.record(
                "chat_cadence_hold",
                {
                    "status": outbox_result.status,
                    "reason": outbox_result.reason,
                    "reply_origin": output_verdict.reply_origin,
                    "chat_cadence_mode": getattr(response_plan, "chat_cadence_mode", None),
                    "text_preview": str(output_verdict.reply_text or "")[:120],
                },
            )
        await self._publish_phase1_event(
            session_key=session_key,
            kind="telegram_chat_cadence_hold",
            trace_id=trace_id,
            message_id=ingress_message_id,
            payload={
                "status": outbox_result.status,
                "reason": outbox_result.reason,
                "chat_cadence_mode": getattr(response_plan, "chat_cadence_mode", None),
                "reply_origin": output_verdict.reply_origin,
                "reply_authority": output_verdict.applied_authority,
                "queued_event": dict(outbox_result.queued_event or {}) if outbox_result.queued_event else None,
            },
        )
        return outbox_result.to_dict()

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
            "profile_rule_read_only_preflight",
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

    def _build_contract_event_payload(
        self,
        *,
        state: RuntimeV2State,
        event_kind: str,
        contract: Optional[dict] = None,
        next_step: Optional[dict] = None,
        verification: Optional[dict] = None,
    ) -> dict:
        contract = contract or {}
        next_step = next_step or {}
        verification = verification or {}
        if not contract and event_kind != "contract_locked":
            contract = state.task_contract or {}
        if not next_step and event_kind in {"step_verified", "need_relock"}:
            next_step = state.next_step_decision or {}
        if not verification and event_kind in {"step_verified", "need_relock"}:
            verification = state.last_verification_result or {}
        return {
            "trace_schema": "contract_runtime_v1",
            "event_kind": event_kind,
            "contract_phase": state.contract_phase,
            "task_id": contract.get("task_id"),
            "goal": contract.get("goal"),
            "success_criteria": contract.get("success_criteria") or [],
            "hard_constraints": contract.get("hard_constraints") or [],
            "risk_level": contract.get("risk_level"),
            "ask_needed": contract.get("ask_needed"),
            "step_id": next_step.get("step_id"),
            "action_type": next_step.get("action_type"),
            "expected_signal": next_step.get("expected_signal"),
            "tool_name": next_step.get("tool_name"),
            "need_relock": verification.get("need_relock", state.need_relock),
            "expected_signal_matched": verification.get("expected_signal_matched"),
            "stop_reason": verification.get("stop_reason"),
            "contract_delta": verification.get("contract_delta") or {},
        }

    def _build_task_conflict_reply(self, state: RuntimeV2State) -> str:
        conflict = state.get_pending_task_conflict()
        if conflict is None:
            return "当前没有待确认的新任务。"
        return (
            "当前已有一个活跃任务。你刚刚又发了一个新的执行任务。\n\n"
            f"新任务：{conflict.incoming_text[:140]}\n\n"
            "用 `/replace` 会结束旧任务并开始新任务；用 `/append` 会把它排到当前任务后面；用 `/cancel` 会保持当前任务不变。"
        )

    def _build_invalid_task_conflict_reply(self) -> str:
        return "当前没有待确认的新任务。"

    def _prepare_subject_gated_host_owned_delivery(
        self,
        *,
        state: RuntimeV2State,
        session_id: str,
        turn_id: str,
        reply_text: str,
        status: str,
        delivery_kind: str = "final",
        authority_source: str = "host_pre_runtime",
        reply_authority: str = "host_response_contract",
        metadata: Optional[dict[str, Any]] = None,
        channel: str = "telegram",
        source_kind: str = "telegram_prepared",
        transport_meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        plan = build_direct_response_plan(
            reply_text,
            kind=status,
            delivery_kind=delivery_kind,
            authority_source=authority_source,
            reply_authority=reply_authority,
            metadata=dict(metadata or {}),
            state=state,
        )
        output_verdict = apply_output_check(plan, state)
        turn_result = TelegramTurnResult(
            status=status,
            state=state,
            reply=TelegramTurnReply(
                reply_text=output_verdict.reply_text,
                delivery_kind=output_verdict.delivery_kind,
                status=status,
            ),
        )
        gate_verdict = None
        subject_gate = self._get_subject_gate()
        if subject_gate is not None:
            gate_verdict = subject_gate.finalize_host_owned_result(
                session_id=session_id,
                turn_id=turn_id,
                result=turn_result,
                state=state,
                evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
            )
            if not gate_verdict.ok:
                blocked_result = TelegramTurnResult(
                    status="subject_gate_finalize_blocked",
                    state=state,
                    reply=TelegramTurnReply(
                        reply_text=gate_verdict.reply_text,
                        delivery_kind="final",
                        status="subject_gate_finalize_blocked",
                    ),
                )
                unified_turn = build_unified_turn_result(
                    state=state,
                    runtime_result=blocked_result,
                    response_plan=plan,
                    output_verdict=output_verdict,
                    metadata={
                        "channel": channel,
                        "source_kind": source_kind,
                        "authority_source": authority_source,
                        "reply_authority": reply_authority,
                        "subject_gate_reason": gate_verdict.reason,
                    },
                )
                unified_egress = build_unified_egress(
                    unified_turn,
                    state,
                    transport_meta=dict(transport_meta or {}),
                )
                return {
                    "response_plan": plan,
                    "output_verdict": output_verdict,
                    "subject_gate_verdict": gate_verdict,
                    "runtime_result": blocked_result,
                    "unified_turn": unified_turn,
                    "unified_egress": unified_egress,
                }

        unified_turn = build_unified_turn_result(
            state=state,
            runtime_result=turn_result,
            response_plan=plan,
            output_verdict=output_verdict,
            metadata={
                "channel": channel,
                "source_kind": source_kind,
                "authority_source": authority_source,
                "reply_authority": reply_authority,
            },
        )
        unified_egress = build_unified_egress(
            unified_turn,
            state,
            transport_meta=dict(transport_meta or {}),
        )
        return {
            "response_plan": plan,
            "output_verdict": output_verdict,
            "subject_gate_verdict": gate_verdict,
            "runtime_result": turn_result,
            "unified_turn": unified_turn,
            "unified_egress": unified_egress,
        }

    async def _apply_pending_task_conflict_resolution(
        self,
        *,
        state: RuntimeV2State,
        resolution: str,
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
        session_key: str,
    ) -> Optional[str]:
        conflict = state.get_pending_task_conflict()
        if conflict is None:
            return None

        if resolution == "replace":
            if self.autonomy_orchestrator is not None and conflict.existing_run_id:
                existing_run = self.autonomy_orchestrator.repository.get(conflict.existing_run_id)
                if existing_run is not None:
                    existing_run.status = AutonomyRunStatus.SUPERSEDED
                    existing_run.current_phase = "superseded"
                    self.autonomy_orchestrator.repository.update(existing_run)
            state.clear_pending_task_conflict()
            state.reset_active_task_context()
            return conflict.incoming_text

        if resolution == "append":
            appended_items = [item for item in (RunItem.from_dict(raw) for raw in conflict.incoming_run_items) if item is not None]
            state.append_run_items(appended_items)
            state.clear_pending_task_conflict()
            await self._publish_phase1_event(
                session_key=session_key,
                kind="telegram_delivery",
                trace_id=trace_id,
                message_id=ingress_message_id,
                payload={
                    "text": "已把新任务追加到当前任务队列。",
                    "delivery_kind": "final",
                    "status": "task_conflict_appended",
                },
            )
            return ""

        if resolution == "cancel":
            state.clear_pending_task_conflict()
            await self._publish_phase1_event(
                session_key=session_key,
                kind="telegram_delivery",
                trace_id=trace_id,
                message_id=ingress_message_id,
                payload={
                    "text": "已取消这次新任务，保持当前任务不变。",
                    "delivery_kind": "final",
                    "status": "task_conflict_cancelled",
                },
            )
            return ""

        return None

    def _get_active_run(self, session_key: str) -> Optional[AutonomyRun]:
        if self.autonomy_orchestrator is None:
            return None
        return self.autonomy_orchestrator.get_active_run(session_key)

    def _get_conflicted_active_run(self, session_key: str) -> Optional[AutonomyRun]:
        return self._get_active_run(session_key)

    def _build_runtime_status_control_reply(self, session_key: str, state: RuntimeV2State) -> str:
        if state.get_pending_task_conflict() is not None:
            return self._build_task_conflict_reply(state)
        active_run = self._get_active_run(session_key)
        if active_run is None:
            return "当前没有运行中的任务。"
        source_state = state
        snapshot = active_run.runtime_state_snapshot or {}
        if snapshot:
            source_state = RuntimeV2State.from_snapshot(snapshot)
        restore_observation = None
        ingress_context = source_state.ingress_context or {}
        restore_payload = ingress_context.get("restore_observation")
        if isinstance(restore_payload, PendingRestoreObservation):
            restore_observation = restore_payload
        elif isinstance(restore_payload, dict) and restore_payload.get("restore_status"):
            restore_observation = PendingRestoreObservation(**restore_payload)
        elif self._pending_restore_observation is not None:
            restore_observation = self._pending_restore_observation
        plan = build_status_response_plan(
            "status",
            source_state,
            assume_active=True,
            restore_observation=restore_observation,
        )
        return plan.reply_text

    def _build_manual_resume_ack_text(self, run: AutonomyRun) -> str:
        snapshot = run.runtime_state_snapshot or {}
        snapshot_state = RuntimeV2State.from_snapshot(snapshot) if snapshot else None
        active_item = snapshot_state.get_active_run_item() if snapshot_state else None
        if active_item is None and snapshot_state is not None:
            active_item = snapshot_state.get_next_pending_run_item()
        if active_item is None:
            return "继续处理当前任务。"
        if active_item.canonical_path:
            target = Path(active_item.canonical_path).name
            if target == active_item.canonical_path and "\\" in active_item.canonical_path:
                target = active_item.canonical_path.rsplit("\\", 1)[-1]
        else:
            target = active_item.description
        return f"继续处理 {target}。"

    def _build_manual_resume_event(self, run: AutonomyRun) -> RunEvent:
        snapshot = run.runtime_state_snapshot or {}
        snapshot_state = RuntimeV2State.from_snapshot(snapshot) if snapshot else None
        active_item = snapshot_state.get_active_run_item() if snapshot_state else None
        if active_item is None and snapshot_state is not None:
            active_item = snapshot_state.get_next_pending_run_item()
        return RunEvent(
            event_type="run_resumed",
            text=self._build_manual_resume_ack_text(run),
            item_id=active_item.item_id if active_item else None,
            item_label=active_item.description if active_item else None,
        )

    def _spawn_manual_resume(self, run_id: str) -> None:
        existing = self._manual_resume_tasks.get(run_id)
        if existing is not None and not existing.done():
            return

        async def _runner() -> None:
            try:
                await self.autonomy_orchestrator.resume_run(run_id, trigger_source="manual")
            except Exception:
                logger.exception("telegram.manual_resume.failed run_id=%s", run_id)
            finally:
                self._manual_resume_tasks.pop(run_id, None)

        task = asyncio.create_task(_runner())
        self._manual_resume_tasks[run_id] = task

    def _prepare_run_items_for_new_task(self, text: str, state: RuntimeV2State) -> list[RunItem]:
        run_items = self._build_run_items_for_request(text, state)
        state.begin_execute_task(text, run_items, state.ingress_context)
        return run_items

    async def _maybe_handle_pending_task_conflict(
        self,
        *,
        update: Update,
        state: RuntimeV2State,
        text: str,
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
        session_key: str,
    ) -> Optional[str]:
        conflict = state.get_pending_task_conflict()
        if conflict is None:
            return None

        await self._send_host_owned_reply(
            update,
            state=state,
            reply_text=self._build_task_conflict_reply(state),
            status="task_conflict_pending",
            delivery_kind="final",
            authority_source="host_pre_runtime",
            reply_authority="host_task_conflict",
            metadata={"conversation_act": "task_conflict"},
        )
        return ""

    async def _maybe_create_task_conflict(
        self,
        *,
        update: Update,
        state: RuntimeV2State,
        ingress=None,
        session_key: str,
        text: str,
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> bool:
        if self._should_bypass_task_conflict_for_pending_artifact_execute(state, ingress):
            return False
        active_run = self._get_conflicted_active_run(session_key)
        if active_run is None:
            return False
        if state.get_pending_task_conflict() is not None:
            return True

        run_items = self._build_run_items_for_request(text, state)
        state.set_pending_task_conflict(
            RunConflictState(
                existing_run_id=active_run.id,
                existing_objective=active_run.objective,
                incoming_text=text,
                incoming_run_items=[item.to_dict() for item in run_items],
            )
        )
        await self._publish_phase1_event(
            session_key=session_key,
            kind="telegram_delivery",
            trace_id=trace_id,
            message_id=ingress_message_id,
            payload={
                "text": self._build_task_conflict_reply(state)[:1000],
                "delivery_kind": "final",
                "status": "task_conflict_pending",
            },
        )
        await self._send_host_owned_reply(
            update,
            state=state,
            reply_text=self._build_task_conflict_reply(state),
            status="task_conflict_pending",
            delivery_kind="final",
            authority_source="host_pre_runtime",
            reply_authority="host_task_conflict",
            metadata={"conversation_act": "task_conflict"},
        )
        return True

    def _build_run_item_started_text(self, item: RunItem) -> str:
        return build_run_item_started_text(item)

    def _build_run_item_verified_text(self, item: RunItem) -> str:
        return build_run_item_verified_text(item)

    def _should_use_run_item_timeline(self, state: RuntimeV2State) -> bool:
        return (state.ingress_context or {}).get("runtime_action") == "execute_task" and bool(state.run_items)

    async def _emit_run_event_message(
        self,
        *,
        state: RuntimeV2State,
        session_key: str,
        event: RunEvent,
        update: Optional[Update],
        chat_id: Optional[int],
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> None:
        delivery_state = self._get_progress_delivery_state(state)
        signature = f"{event.event_type}:{event.item_id or ''}:{event.text}"
        if delivery_state.get("last_run_event_signature") == signature:
            return
        await self._publish_phase1_event(
            session_key=session_key,
            kind="telegram_progress_delivery",
            trace_id=trace_id,
            message_id=ingress_message_id,
            payload={
                "phase_key": event.event_type,
                "text": event.text[:300],
                "delivery_mode": "send",
                "item_id": event.item_id,
            },
        )
        if isinstance(chat_id, int):
            await self._send_chat_message(chat_id, event.text, finalize_evidence=False)
        elif update is not None:
            await self._send_reply(update, event.text, finalize_evidence=False)
        delivery_state["last_run_event_signature"] = signature

    async def _emit_pending_run_events(
        self,
        *,
        state: RuntimeV2State,
        session_key: str,
        update: Optional[Update],
        chat_id: Optional[int],
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> int:
        if not state.has_pending_run_events():
            return 0
        sent = 0
        for event in state.pop_run_events():
            await self._emit_run_event_message(
                state=state,
                session_key=session_key,
                event=event,
                update=update,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )
            sent += 1
        return sent

    async def _ensure_active_run_item_message(
        self,
        *,
        state: RuntimeV2State,
        session_key: str,
        update: Optional[Update],
        chat_id: Optional[int],
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> Optional[RunItem]:
        item = state.ensure_active_run_item_started()
        await self._emit_pending_run_events(
            state=state,
            session_key=session_key,
            update=update,
            chat_id=chat_id,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
        )
        return item

    async def _emit_verified_run_item_message(
        self,
        *,
        state: RuntimeV2State,
        session_key: str,
        item: RunItem,
        update: Optional[Update],
        chat_id: Optional[int],
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> None:
        await self._emit_run_event_message(
            state=state,
            session_key=session_key,
            event=RunEvent(
                event_type="item_verified",
                text=self._build_run_item_verified_text(item),
                item_id=item.item_id,
                item_label=item.description,
            ),
            update=update,
            chat_id=chat_id,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
        )

    async def _emit_newly_verified_run_items(
        self,
        *,
        state: RuntimeV2State,
        session_key: str,
        update: Optional[Update],
        chat_id: Optional[int],
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> None:
        await self._emit_pending_run_events(
            state=state,
            session_key=session_key,
            update=update,
            chat_id=chat_id,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
        )

    def _build_manual_resume_stall_reply(self, state: RuntimeV2State) -> str:
        summary = state.current_frontier_summary() if hasattr(state, "current_frontier_summary") else state.get_run_item_status_summary()
        completed = list(summary.get("completed") or [])
        active = summary.get("active")
        pending = list(summary.get("pending") or [])
        blocked = list(summary.get("blocked") or [])
        reason = str((state.last_verification_result or {}).get("reason") or "").strip()
        details = []
        if completed:
            details.append(f"已完成：{', '.join(completed)}。")
        if blocked:
            details.append(f"当前卡住：{', '.join(blocked)}。")
        elif active:
            details.append(f"当前卡住：{active}。")
        if pending:
            details.append(f"还未开始：{', '.join(pending)}。")
        if reason:
            details.append(f"失败原因：{reason}。")
        return (
            "这次继续后仍没有新的可验证进展，我先停下来，避免继续空转。\n\n"
            f"{' '.join(details)}\n\n"
            "你回复“继续”可以再试一次，或者把任务拆小后再试。"
        )

    def _ensure_phase1_bus(self) -> None:
        if self._phase1_bus_ready:
            return

        async def append_to_session_log(event: BusEvent) -> None:
            self._session_log_manager.append(event)

        self._session_worker_pool.register_handler(append_to_session_log)
        self._session_worker_pool.start()
        self._phase1_bus_ready = True

    async def _publish_phase1_event(
        self,
        *,
        session_key: str,
        kind: str,
        payload: dict,
        trace_id: Optional[str] = None,
        message_id: Optional[int] = None,
    ) -> None:
        self._ensure_phase1_bus()
        await self._message_bus.publish(
            BusEvent(
                session_key=session_key,
                kind=kind,
                payload=payload,
                channel="telegram",
                trace_id=trace_id,
                message_id=message_id,
            )
        )

    def _get_runtime_v2_loop(self):
        if not self.use_runtime_v2:
            return None
        if self.telegram_runtime_fallback_runner is None:
            self.telegram_runtime_fallback_runner = TelegramRuntimeFallbackRunner()
            self.runtime_v2_fallback_runner = self.telegram_runtime_fallback_runner
        if self.runtime_v2_loop is None:
            self.runtime_v2_loop = self.telegram_runtime_fallback_runner.get_loop()
        return self.runtime_v2_loop

    def _get_semantic_parse_client(self) -> Optional[Any]:
        if self._semantic_parse_client is not None:
            return self._semantic_parse_client
        try:
            config = get_config()
            chat_cfg = config.get_llm_config_for_use_case("chat")
            provider = str(chat_cfg.get("provider") or config.llm.get("default_provider") or "").strip() or None
            model = str(chat_cfg.get("model") or config.llm.get("default_model") or "").strip() or None
            if not provider and not model:
                return None
            self._semantic_parse_client = get_llm_client(provider=provider, model=model)
        except Exception as exc:
            logger.warning("runtime_v2.semantic_parse_client_unavailable err=%s", exc)
            self._semantic_parse_client = None
        return self._semantic_parse_client

    def _get_runtime_state(self, session_key: str) -> RuntimeV2State:
        state = self._runtime_states.get(session_key)
        runtime_loop = self.runtime_v2_loop
        if state is None and runtime_loop is not None:
            state = runtime_loop._states.get(session_key)
        if state is None:
            state = RuntimeV2State(session_id=session_key)
            state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
            self._runtime_states[session_key] = state
        elif session_key not in self._runtime_states:
            self._runtime_states[session_key] = state
        if runtime_loop is not None:
            runtime_loop._states[session_key] = state
        return state

    def _restore_runtime_state_snapshot(self, session_key: str, snapshot: Optional[dict]) -> RuntimeV2State:
        if snapshot:
            state = RuntimeV2State.from_snapshot(snapshot)
        else:
            state = RuntimeV2State(session_id=session_key)
            state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
        self._runtime_states[session_key] = state
        runtime_loop = self._get_runtime_v2_loop()
        if runtime_loop is not None:
            runtime_loop._states[session_key] = state
        return state

    def _chunk_telegram_text(self, text: str, *, limit: int = TELEGRAM_TEXT_CHUNK_LIMIT) -> list[str]:
        body = str(text or "")
        if len(body) <= limit:
            return [body]

        chunks: list[str] = []
        remaining = body
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n", 0, limit)
            if split_at < max(1, limit // 2):
                split_at = limit
            chunk = remaining[:split_at].rstrip()
            if not chunk:
                chunk = remaining[:limit]
                split_at = len(chunk)
            chunks.append(chunk)
            remaining = remaining[split_at:].lstrip("\n")
        return chunks

    def _capture_telegram_outbox_record(
        self,
        sent_message: Any,
        *,
        text_length: int,
        text_preview: Optional[str] = None,
        finalize_evidence: bool,
    ) -> None:
        if not sent_message or not _EVIDENCE_COLLECTOR_AVAILABLE:
            return
        try:
            preview = str(text_preview or "").strip()
            collector = get_evidence_collector()
            collector.capture_outbox_record(
                {
                    "chat_id": sent_message.chat.id if sent_message.chat else None,
                    "message_id": sent_message.message_id,
                    "date": sent_message.date.isoformat() if sent_message.date else None,
                    "text_length": text_length,
                    "final_text_preview": preview[:200] or None,
                    "final_text_hash": hashlib.sha256(preview.encode("utf-8")).hexdigest()[:16] if preview else None,
                    "success": True,
                }
            )
            if finalize_evidence:
                sample = collector.finalize_sample()
                if sample and _DEVELOPMENTAL_WRITEBACK_AVAILABLE:
                    try:
                        record_developmental_projection_from_finalized_sample(
                            sample=sample,
                            sample_artifacts_dir=collector.artifacts_dir,
                        )
                    except Exception as e:
                        logger.warning(f"[MVP16-DEVELOPMENTAL] Failed to sync finalized direct sample: {e}")
        except Exception as e:
            logger.warning(f"[E4-EVIDENCE] Failed to capture direct outbox_record: {e}")

    def _remember_session_transport_binding(self, session_key: str, chat_id: Optional[int]) -> None:
        if isinstance(chat_id, int):
            self._chat_id_by_session[session_key] = int(chat_id)

    def _resolve_proactive_chat_id(self, session_key: str, explicit_chat_id: Optional[int] = None) -> Optional[int]:
        if isinstance(explicit_chat_id, int):
            return int(explicit_chat_id)
        mapped = self._chat_id_by_session.get(session_key)
        if isinstance(mapped, int):
            return int(mapped)
        parts = str(session_key or "").split(":")
        if len(parts) == 3 and parts[0] == "telegram" and parts[1] in {"dm", "group"}:
            try:
                return int(parts[2])
            except (TypeError, ValueError):
                return None
        return None

    def _iter_proactive_telegram_sessions(self) -> list[str]:
        session_keys = set(self._runtime_states.keys()) | set(self._chat_id_by_session.keys())
        return sorted(
            session_key
            for session_key in session_keys
            if self._resolve_proactive_chat_id(session_key) is not None
        )

    def _build_proactive_telegram_enable_policy(self) -> ProactiveTelegramEnablePolicy:
        allowed_chat_ids = (
            frozenset(self._mvp12_proactive_allowed_chat_ids)
            if self._mvp12_proactive_allowed_chat_ids is not None
            else None
        )
        return ProactiveTelegramEnablePolicy(
            enabled=self._mvp12_proactive_telegram_autodrain_enabled,
            allowed_chat_ids=allowed_chat_ids,
            allowed_session_prefixes=tuple(self._mvp12_proactive_allowed_session_prefixes or ("telegram:dm:",)),
            min_recent_user_turns=self._mvp12_proactive_min_recent_user_turns,
            min_recent_assistant_replies=self._mvp12_proactive_min_recent_assistant_replies,
        )

    async def run_host_governed_proactive_telegram_cycle(
        self,
        session_key: str,
        *,
        now_ts: Optional[float] = None,
        observation_source: str = "direct_real",
        live_mode: bool = False,
        max_events: Optional[int] = None,
        enforce_enable_policy: bool = False,
    ) -> dict[str, Any]:
        runtime_loop = self._get_runtime_v2_loop()
        state = self._get_runtime_state(session_key)
        resolved_chat_id = self._resolve_proactive_chat_id(session_key)
        enable_policy_verdict = None
        if live_mode and enforce_enable_policy:
            enable_policy_verdict = evaluate_proactive_telegram_enable_policy(
                session_id=session_key,
                state=state,
                chat_id=resolved_chat_id,
                policy=self._build_proactive_telegram_enable_policy(),
            )
            if hasattr(state, "record"):
                state.record("proactive_followup_enable_policy", enable_policy_verdict.to_dict())
            if not enable_policy_verdict.allowed:
                return {
                    "status": "held",
                    "reason": f"enable_policy:{enable_policy_verdict.reason}",
                    "enable_policy": enable_policy_verdict.to_dict(),
                    "scheduler_result": None,
                    "delivery_result": None,
                    "outbox_result": None,
                    "transport_gate": {},
                    "transport_result": None,
                }
        cycle_result = await run_host_governed_proactive_cycle(
            session_id=session_key,
            state=state,
            proto_self_runtime=getattr(runtime_loop, "proto_self_runtime", None),
            transport_drain=lambda sid, limit: self.drain_pending_proactive_outbox_to_telegram(
                sid,
                max_events=(max_events if isinstance(max_events, int) and max_events > 0 else limit),
                finalize_evidence=False,
            ),
            now_ts=now_ts,
            scheduler_min_idle_seconds=self._mvp12_proactive_scheduler_idle_seconds,
            transport_min_idle_seconds=self._mvp12_proactive_transport_idle_seconds,
            assistant_reply_cooldown_seconds=self._mvp12_proactive_reply_cooldown_seconds,
            max_transport_events=(
                max_events if isinstance(max_events, int) and max_events > 0 else self._mvp12_proactive_max_events_per_tick
            ),
            observation_source=observation_source,
            controlled_mode=not live_mode,
        )
        payload = cycle_result.to_dict()
        if enable_policy_verdict is not None:
            payload["enable_policy"] = enable_policy_verdict.to_dict()
        if hasattr(state, "record"):
            state.record(
                "proactive_followup_host_cycle",
                {
                    "status": payload.get("status"),
                    "reason": payload.get("reason"),
                    "transport_status": (payload.get("transport_result") or {}).get("status"),
                    "transport_reason": (payload.get("transport_result") or {}).get("reason"),
                },
            )
        return payload

    async def _run_proactive_telegram_autodrain_loop(self) -> None:
        logger.info(
            "telegram.proactive_autodrain.loop.start tick_seconds=%.1f scheduler_idle=%.1f transport_idle=%.1f cooldown=%.1f",
            self._mvp12_proactive_telegram_tick_seconds,
            self._mvp12_proactive_scheduler_idle_seconds,
            self._mvp12_proactive_transport_idle_seconds,
            self._mvp12_proactive_reply_cooldown_seconds,
        )
        try:
            while True:
                await asyncio.sleep(max(1.0, float(self._mvp12_proactive_telegram_tick_seconds)))
                for session_key in self._iter_proactive_telegram_sessions():
                    try:
                        result = await self.run_host_governed_proactive_telegram_cycle(
                            session_key,
                            live_mode=True,
                            observation_source="direct_real",
                            enforce_enable_policy=True,
                        )
                    except Exception as e:
                        logger.exception("telegram.proactive_autodrain.failed session=%s err=%s", session_key, e)
                        continue
                    if result.get("status") in {"sent", "partial"}:
                        logger.info(
                            "telegram.proactive_autodrain.sent session=%s status=%s reason=%s",
                            session_key,
                            result.get("status"),
                            result.get("reason"),
                        )
        except asyncio.CancelledError:
            logger.info("telegram.proactive_autodrain.loop.stop")
            raise

    def _build_recent_read_followup_reply(self, state: RuntimeV2State, text: str) -> Optional[str]:
        snapshot = getattr(state, "last_delivered_evidence_context", None) or getattr(state, "last_evidence_read_result", None)
        if not isinstance(snapshot, dict):
            return None
        delivered_at = float(snapshot.get("delivered_at") or snapshot.get("observed_at") or 0.0)
        if delivered_at and (time.time() - delivered_at) > RECENT_EVIDENCE_RESULT_TTL_SECONDS:
            return None

        normalized = normalize_user_turn(text)
        if normalized.probe_key not in READ_LIST_FOLLOWUP_PROBE_KEYS:
            return None

        request_kind = str(snapshot.get("request_kind") or "")
        body = str(snapshot.get("body") or "").strip()
        if not body:
            return None

        if request_kind == "directory_listing":
            entries = _extract_directory_listing_entries(body)
            if not entries:
                return "目录是空的。"
            if snapshot.get("truncated") or snapshot.get("delivery_was_chunked"):
                return f"不是空的，内容较长，已分段发送。目录内容如下：\n{body}"
            return f"不是空的。目录内容如下：\n{body}"

        prefix = "上条结果如下："
        if snapshot.get("truncated") or snapshot.get("delivery_was_chunked"):
            prefix = "上条结果内容较长，已分段发送。结果如下："
        return f"{prefix}\n{body}"

    async def _send_chat_message(self, chat_id: int, text: str, *, finalize_evidence: bool = True):
        if not self.app or not getattr(self.app, "bot", None):
            return {"sent_count": 0, "was_chunked": False, "last_message_id": None, "message_records": []}

        chunks = self._chunk_telegram_text(text)
        sent_count = 0
        last_message_id = None
        message_records: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            sent_message = None
            try:
                sent_message = await self.app.bot.send_message(chat_id=chat_id, text=chunk)
            except Exception as e:
                logger.warning("telegram.direct_send.failed chat_id=%s err=%s", chat_id, e)
                continue

            sent_count += 1
            last_message_id = getattr(sent_message, "message_id", None)
            message_records.append(
                {
                    "chat_id": sent_message.chat.id if getattr(sent_message, "chat", None) else chat_id,
                    "message_id": getattr(sent_message, "message_id", None),
                    "date": sent_message.date.isoformat() if getattr(sent_message, "date", None) else None,
                    "text_length": len(chunk),
                    "success": True,
                }
            )
            self._capture_telegram_outbox_record(
                sent_message,
                text_length=len(chunk),
                text_preview=chunk,
                finalize_evidence=finalize_evidence and index == len(chunks) - 1,
            )

        return {
            "sent_count": sent_count,
            "was_chunked": len(chunks) > 1,
            "last_message_id": last_message_id,
            "message_records": message_records,
        }

    async def drain_pending_proactive_outbox_to_telegram(
        self,
        session_key: str,
        *,
        chat_id: Optional[int] = None,
        max_events: Optional[int] = None,
        finalize_evidence: bool = False,
    ) -> dict[str, Any]:
        state = self._get_runtime_state(session_key)
        if not state.has_pending_proactive_outbox_events():
            return {
                "status": "held",
                "reason": "no_pending_outbox_events",
                "sent_records": [],
                "remaining_events": [],
            }
        if not self.app or not getattr(self.app, "bot", None):
            return {
                "status": "held",
                "reason": "telegram_transport_unavailable",
                "sent_records": [],
                "remaining_events": state.peek_proactive_outbox_events(),
            }

        resolved_chat_id = self._resolve_proactive_chat_id(session_key, explicit_chat_id=chat_id)
        if not isinstance(resolved_chat_id, int):
            return {
                "status": "held",
                "reason": "missing_telegram_chat_id",
                "sent_records": [],
                "remaining_events": state.peek_proactive_outbox_events(),
            }
        if not self.is_allowed(resolved_chat_id):
            return {
                "status": "held",
                "reason": "chat_not_allowed",
                "sent_records": [],
                "remaining_events": state.peek_proactive_outbox_events(),
            }

        queued_events = state.pop_proactive_outbox_events()
        if isinstance(max_events, int) and max_events > 0 and len(queued_events) > max_events:
            active_events = queued_events[:max_events]
            deferred_events = queued_events[max_events:]
        else:
            active_events = queued_events
            deferred_events = []

        sent_records: list[dict[str, Any]] = []
        remaining_events: list[dict[str, Any]] = list(deferred_events)
        context_store = get_session_context_store()
        chat_state = state.get_chat_state()

        for index, event in enumerate(active_events):
            reply_text = str(event.get("reply_text") or "").strip()
            if not reply_text:
                state.record(
                    "proactive_followup_transport",
                    {
                        "status": "dropped_empty",
                        "initiative_candidate_id": event.get("initiative_candidate_id"),
                    },
                )
                continue

            request_id = str(event.get("initiative_candidate_id") or "").strip() or None
            delivery_identity = self._build_delivery_identity(
                session_key=session_key,
                ingress_message_id=None,
                reply_text=reply_text,
                request_id=request_id,
                delivery_kind="proactive",
            )
            if self._delivery_dedupe_policy.should_suppress(delivery_identity):
                state.record(
                    "proactive_followup_transport",
                    {
                        "status": "duplicate_suppressed",
                        "initiative_candidate_id": event.get("initiative_candidate_id"),
                        "reply_origin": event.get("reply_origin"),
                        "reply_authority": event.get("reply_authority"),
                    },
                )
                continue

            send_result = await self._send_chat_message(
                resolved_chat_id,
                reply_text,
                finalize_evidence=finalize_evidence,
            )
            if int(send_result.get("sent_count") or 0) <= 0:
                remaining_events.append(dict(event))
                remaining_events.extend(dict(item) for item in active_events[index + 1 :])
                break

            self._delivery_dedupe_policy.mark_sent(delivery_identity)
            context_store.add_turn(session_key, "assistant", reply_text)
            chat_state.finalize_turn(assistant_reply=reply_text, chat_act="thread_continue")
            sent_record = {
                "schema_version": "mvp12.telegram_outbox_record.v1",
                "session_id": session_key,
                "chat_id": resolved_chat_id,
                "transport_source": "telegram",
                "delivery_status": "sent",
                "outbox_status": "sent",
                "reply_text": reply_text,
                "text_length": event.get("text_length") or len(reply_text),
                "reply_authority": event.get("reply_authority"),
                "reply_origin": event.get("reply_origin"),
                "authority_source": event.get("authority_source"),
                "chat_cadence_mode": event.get("chat_cadence_mode"),
                "chat_expression_hint": dict(event.get("chat_expression_hint") or {}),
                "response_tendency_summary": dict(event.get("response_tendency_summary") or {}),
                "initiative_mode": event.get("initiative_mode"),
                "initiative_candidate_id": event.get("initiative_candidate_id"),
                "initiative_source_cycle": event.get("initiative_source_cycle"),
                "initiative_source_hash": event.get("initiative_source_hash"),
                "initiative_score": event.get("initiative_score"),
                "outbox_lane": event.get("outbox_lane"),
                "last_message_id": send_result.get("last_message_id"),
                "was_chunked": bool(send_result.get("was_chunked")),
                "message_records": list(send_result.get("message_records") or []),
                "queued_event": dict(event),
            }
            sent_records.append(sent_record)
            state.record(
                "proactive_followup_transport",
                {
                    "status": "sent",
                    "initiative_candidate_id": sent_record.get("initiative_candidate_id"),
                    "reply_origin": sent_record.get("reply_origin"),
                    "reply_authority": sent_record.get("reply_authority"),
                    "message_id": sent_record.get("last_message_id"),
                    "text_preview": reply_text[:120],
                },
            )
            await self._publish_phase1_event(
                session_key=session_key,
                kind="telegram_proactive_delivery",
                trace_id=request_id,
                message_id=sent_record.get("last_message_id"),
                payload={
                    "chat_id": resolved_chat_id,
                    "reply_text": reply_text[:1000],
                    "reply_authority": sent_record.get("reply_authority"),
                    "reply_origin": sent_record.get("reply_origin"),
                    "chat_cadence_mode": sent_record.get("chat_cadence_mode"),
                    "initiative_candidate_id": sent_record.get("initiative_candidate_id"),
                    "outbox_lane": sent_record.get("outbox_lane"),
                    "transport_source": "telegram",
                },
            )

        if hasattr(state, "set_proactive_outbox_events"):
            state.set_proactive_outbox_events(remaining_events)
        else:
            for event in remaining_events:
                state.push_proactive_outbox_event(event)

        if sent_records and not remaining_events:
            status = "sent"
            reason = "ok"
        elif sent_records:
            status = "partial"
            reason = "send_failed_midway"
        else:
            status = "held"
            reason = "send_failed"
        return {
            "status": status,
            "reason": reason,
            "chat_id": resolved_chat_id,
            "sent_records": sent_records,
            "remaining_events": state.peek_proactive_outbox_events(),
        }

    def _select_autonomy_executor_kind(self, ingress, state) -> AutonomyExecutorKind:
        return (
            AutonomyExecutorKind.CONTRACT_EXECUTE
            if self._should_use_native_loop(ingress, state)
            else AutonomyExecutorKind.GENERIC_RUNTIME
        )

    def _is_manual_resumable_blocked_run(self, run: Optional[AutonomyRun]) -> bool:
        if run is None or run.status != AutonomyRunStatus.BLOCKED:
            return False
        return run.hard_blocker_reason in {
            AutonomyStopReason.TRANSIENT_RETRY_BUDGET_EXCEEDED.value,
            AutonomyStopReason.NO_PROGRESS_STALL_DETECTED.value,
            AutonomyStopReason.AUTONOMY_SAFETY_CAP_EXCEEDED.value,
        }

    def _sync_autonomy_context(
        self,
        state: RuntimeV2State,
        run: AutonomyRun,
        *,
        status: Optional[str] = None,
        finish_reason: Optional[str] = None,
    ) -> None:
        previous_progress_delivery = None
        if isinstance(state.autonomy_context, dict):
            previous_progress_delivery = state.autonomy_context.get("progress_delivery")
        state.autonomy_context = {
            "run_id": run.id,
            "status": status or run.status.value,
            "executor_kind": run.executor_kind.value,
            "current_phase": run.current_phase,
            "resume_count": run.resume_count,
            "hard_blocker_reason": run.hard_blocker_reason,
        }
        if isinstance(previous_progress_delivery, dict):
            state.autonomy_context["progress_delivery"] = previous_progress_delivery
        if finish_reason:
            state.autonomy_context["finish_reason"] = finish_reason

    def _get_progress_delivery_state(self, state: RuntimeV2State) -> dict:
        if not isinstance(state.autonomy_context, dict):
            state.autonomy_context = {}
        progress_delivery = state.autonomy_context.get("progress_delivery")
        if not isinstance(progress_delivery, dict):
            progress_delivery = {}
            state.autonomy_context["progress_delivery"] = progress_delivery
        return progress_delivery

    def _reset_autonomy_delivery_state(self, state: RuntimeV2State) -> None:
        state.final_sent = False
        progress_delivery = self._get_progress_delivery_state(state)
        progress_delivery.clear()

    def _get_transient_retry_limit(self, state: RuntimeV2State) -> int:
        status_code = ((state.last_model_action or {}).get("status_code"))
        if status_code == 429:
            return self.autonomy_rate_limited_retry_limit
        return self.autonomy_transient_retry_limit

    def _get_transient_retry_backoff_seconds(self, state: RuntimeV2State, run: AutonomyRun) -> int:
        raw = state.last_model_action or {}
        status_code = raw.get("status_code")
        suggested_retry_after = raw.get("retry_after_seconds")
        try:
            suggested_retry_after = int(suggested_retry_after) if suggested_retry_after is not None else 0
        except (TypeError, ValueError):
            suggested_retry_after = 0
        attempt_index = max(run.resume_count + 1, 1)
        if status_code == 429:
            return max(suggested_retry_after, min(30 * attempt_index, 180))
        return max(suggested_retry_after, min(15 * attempt_index, 60))

    def _clear_no_progress_tracking(self, run: AutonomyRun) -> None:
        for key in (
            "no_progress_signature",
            "no_progress_count",
            "no_progress_reason",
            "no_progress_pending_outputs",
        ):
            run.metadata.pop(key, None)

    def _compute_no_progress_signature(self, state: RuntimeV2State, result: TelegramTurnResult) -> Optional[str]:
        if result.status != "resumable_pause":
            return None
        if getattr(result, "finish_reason", None) != AutonomyStopReason.MAX_STEPS_EXHAUSTED.value:
            return None

        verification = state.last_verification_result or {}
        run_items = state.get_run_items()
        if run_items:
            active_item = state.get_active_run_item()
            progress_marker = state.capture_active_run_item_progress_marker() or {}
            marker = {
                "finish_reason": getattr(result, "finish_reason", None),
                "verification_reason": verification.get("reason"),
                "active_item_id": active_item.item_id if active_item else state.active_item_id,
                "active_item_status": active_item.status if active_item else None,
                "active_item_path": active_item.canonical_path if active_item else None,
                "active_item_attempt_count": active_item.attempt_count if active_item else None,
                "progress_marker": progress_marker,
                "completed_items": sorted(
                    item.description for item in run_items if item.status == "verified"
                ),
                "remaining_items": sorted(
                    item.description for item in run_items if item.status != "verified"
                ),
            }
        else:
            evidence = verification.get("evidence") or {}
            marker = {
                "finish_reason": getattr(result, "finish_reason", None),
                "verification_reason": verification.get("reason"),
                "current_step": state.current_step,
                "last_tool_path": ((state.last_tool_result or {}).get("metadata") or {}).get("path"),
                "missing_outputs": evidence.get("missing_outputs") or [],
                "stale_outputs": evidence.get("stale_outputs") or [],
            }
        return json.dumps(marker, ensure_ascii=False, sort_keys=True)

    def _record_no_progress_state(self, run: AutonomyRun, state: RuntimeV2State, result: TelegramTurnResult) -> int:
        signature = self._compute_no_progress_signature(state, result)
        if not signature:
            self._clear_no_progress_tracking(run)
            return 0

        previous_signature = str(run.metadata.get("no_progress_signature") or "")
        count = int(run.metadata.get("no_progress_count") or 0)
        count = (count + 1) if signature == previous_signature else 1

        run.metadata["no_progress_signature"] = signature
        run.metadata["no_progress_count"] = count
        run.metadata["no_progress_reason"] = (state.last_verification_result or {}).get("reason")
        run.metadata["no_progress_pending_outputs"] = [
            item.description
            for item in state.get_run_items()
            if item.status != "verified"
        ]
        return count

    def _build_no_progress_blocked_reply(self, state: RuntimeV2State) -> str:
        summary = state.get_run_item_status_summary()
        completed = list(summary.get("completed") or [])
        active = summary.get("active")
        pending = list(summary.get("pending") or [])
        blocked = list(summary.get("blocked") or [])
        details = []
        if completed:
            details.append(f"已完成：{', '.join(completed)}。")
        if blocked:
            details.append(f"当前卡住：{', '.join(blocked)}。")
        elif active:
            details.append(f"当前卡住：{active}。")
        if pending:
            details.append(f"还未开始：{', '.join(pending)}。")
        if not details:
            verification = state.last_verification_result or {}
            reason = str(verification.get("reason") or "").strip()
            if reason:
                details.append(f"当前卡点：{reason}。")
            else:
                details.append("当前步骤连续多次没有产生新的可验证结果。")
        return (
            "这个任务在同一阶段连续多次没有新进展，我先停下来，避免继续空转。\n\n"
            f"{' '.join(details)}\n\n"
            "你回复“继续”可以再试一次，或者把任务拆小后再试。"
        )

    async def _maybe_block_no_progress_run(
        self,
        *,
        run: AutonomyRun,
        state: RuntimeV2State,
        result: TelegramTurnResult,
        chat_id: Optional[int],
    ) -> Optional[TelegramTurnResult]:
        repeat_count = self._record_no_progress_state(run, state, result)
        if repeat_count < self.autonomy_no_progress_retry_limit:
            return None

        blocked_text = self._build_no_progress_blocked_reply(state)
        state.task_status = "blocked"
        state.waiting_for_user_input = False
        if isinstance(chat_id, int):
            await self._publish_phase1_event(
                session_key=run.session_key,
                kind="telegram_delivery",
                trace_id=run.metadata.get("trace_id"),
                message_id=run.metadata.get("ingress_message_id"),
                payload={
                    "text": blocked_text[:1000],
                    "delivery_kind": "final",
                    "status": "blocked",
                },
            )
            await self._send_chat_message(chat_id, blocked_text, finalize_evidence=True)
            state.final_sent = True

        return TelegramTurnResult(
            status="blocked",
            state=state,
            reply=TelegramTurnReply(
                reply_text=blocked_text,
                delivery_kind="final",
                status="blocked",
            ),
            finish_reason=AutonomyStopReason.NO_PROGRESS_STALL_DETECTED.value,
            checkpoint_payload=run.checkpoint_payload,
        )

    def _build_autonomy_progress_text(self, phase_key: str, payload: Optional[dict] = None) -> Optional[str]:
        payload = dict(payload or {})
        resolved_target = payload.get("resolved_target") or {}
        target_name = (
            payload.get("target_name")
            or resolved_target.get("filename")
            or payload.get("target_path")
            or payload.get("source_artifact_id")
        )
        tool_name = payload.get("tool_name")
        if phase_key == "locking_goal":
            return "我先确认目标和约束。"
        if phase_key == "reading_context":
            if target_name:
                return f"我先检查 {target_name} 和相关上下文。"
            return "我先检查目标路径和相关上下文。"
        if phase_key == "planning_current_slice":
            return "我先规划当前这一段执行。"
        if phase_key == "executing_changes":
            if tool_name == "file":
                return "我开始处理文件和内容。"
            if tool_name == "shell":
                return "我开始执行必要的检查。"
            if tool_name == "python":
                return "我开始运行需要的脚本。"
            return "我开始推进当前步骤。"
        if phase_key == "verifying":
            return "我先核对结果。"
        if phase_key == "awaiting_confirmation":
            return "这一步需要你确认后我再继续。"
        if phase_key == "blocked":
            return "这里卡住了，我先停下来整理阻塞点。"
        return None

    async def _send_autonomy_progress_update(
        self,
        *,
        state: RuntimeV2State,
        phase_key: str,
        text: Optional[str],
        update: Optional[Update] = None,
        chat_id: Optional[int] = None,
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
    ) -> bool:
        if not text or state.final_sent:
            return False
        progress_delivery = self._get_progress_delivery_state(state)
        if (
            progress_delivery.get("last_phase_key") == phase_key
            and progress_delivery.get("last_text") == text
        ):
            return False

        progress_chat_id = progress_delivery.get("chat_id")
        if not isinstance(progress_chat_id, int):
            if isinstance(chat_id, int):
                progress_chat_id = chat_id
            elif update is not None and getattr(update, "effective_chat", None) is not None:
                progress_chat_id = update.effective_chat.id

        sent_message = None
        existing_message_id = progress_delivery.get("message_id")
        delivery_mode = "send"
        if self.app and getattr(self.app, "bot", None) and isinstance(progress_chat_id, int) and isinstance(existing_message_id, int):
            try:
                await self.app.bot.edit_message_text(
                    chat_id=progress_chat_id,
                    message_id=existing_message_id,
                    text=text,
                )
                delivery_mode = "edit"
            except Exception:
                logger.warning(
                    "telegram.progress_edit.failed session=%s chat_id=%s message_id=%s phase=%s",
                    state.session_id,
                    progress_chat_id,
                    existing_message_id,
                    phase_key,
                    exc_info=True,
                )
                existing_message_id = None

        if existing_message_id is None:
            try:
                if self.app and getattr(self.app, "bot", None) and isinstance(progress_chat_id, int):
                    sent_message = await self.app.bot.send_message(chat_id=progress_chat_id, text=text)
                elif update is not None:
                    sent_message = await update.message.reply_text(text)
                else:
                    return False
            except Exception as e:
                logger.warning("telegram.progress_send.failed session=%s err=%s", state.session_id, e)
                return False

            progress_delivery["message_id"] = sent_message.message_id if sent_message else None
            progress_delivery["chat_id"] = (
                sent_message.chat.id if sent_message and sent_message.chat else progress_chat_id
            )

        await self._publish_phase1_event(
            session_key=state.session_id,
            kind="telegram_progress_delivery",
            trace_id=trace_id,
            message_id=progress_delivery.get("message_id") or ingress_message_id,
            payload={
                "phase_key": phase_key,
                "text": text[:300],
                "delivery_mode": delivery_mode,
            },
        )
        progress_delivery["last_phase_key"] = phase_key
        progress_delivery["last_text"] = text
        progress_delivery["last_sent_at"] = time.time()
        return True

    def _build_transient_retry_exhausted_reply(self) -> str:
        return (
            "模型决策服务连续多次临时失败，我先停止自动重试，避免一直空转。\n\n"
            "你稍后回复“继续”可以从当前任务恢复，或者把任务拆小后再试。"
        )

    async def _deliver_runtime_progress_events(
        self,
        *,
        state: RuntimeV2State,
        update: Optional[Update] = None,
        chat_id: Optional[int] = None,
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
    ) -> int:
        if self._should_use_run_item_timeline(state):
            state.pop_progress_events()
            return 0
        if not state.has_pending_progress_events():
            return 0
        events = state.pop_progress_events()
        sent = 0
        for event in events:
            if not isinstance(event, ProgressEvent):
                continue
            if is_terminal_event(event.event_type):
                continue
            if await self._send_autonomy_progress_update(
                state=state,
                phase_key=event.event_type.value,
                text=event.message,
                update=update,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            ):
                sent += 1
        return sent

    def _build_autonomy_outcome(
        self,
        *,
        run: AutonomyRun,
        state: RuntimeV2State,
        result: TelegramTurnResult,
        default_phase: str,
    ) -> AutonomySliceOutcome:
        finish_reason = getattr(result, "finish_reason", None)
        status_map = {
            "resumable_pause": AutonomyRunStatus.RESUMABLE_PAUSE,
            "waiting_input": AutonomyRunStatus.WAITING_USER_INPUT,
            "blocked": AutonomyRunStatus.BLOCKED,
            "failed": AutonomyRunStatus.FAILED,
            "completed_verified": AutonomyRunStatus.COMPLETED,
            "completed": AutonomyRunStatus.COMPLETED,
            "chat": AutonomyRunStatus.COMPLETED,
        }
        run_status = status_map.get(result.status, AutonomyRunStatus.FAILED)
        if run_status == AutonomyRunStatus.RESUMABLE_PAUSE:
            current_phase = "planning_current_slice"
        elif run_status == AutonomyRunStatus.WAITING_USER_INPUT:
            current_phase = "awaiting_confirmation"
        elif run_status == AutonomyRunStatus.BLOCKED:
            current_phase = "blocked"
        elif run_status == AutonomyRunStatus.COMPLETED:
            current_phase = "completed"
        else:
            current_phase = default_phase
        self._sync_autonomy_context(state, run, status=run_status.value, finish_reason=finish_reason)
        return AutonomySliceOutcome(
            status=run_status,
            stop_reason=finish_reason,
            current_phase=current_phase,
            checkpoint_payload=getattr(result, "checkpoint_payload", None) or {},
            runtime_state_snapshot=state.to_snapshot(),
            last_result_summary={
                "status": result.status,
                "finish_reason": finish_reason,
                "reply_text": result.reply_text,
                "delivery_kind": result.delivery_kind,
                "current_step": state.current_step,
                "status_code": (state.last_model_action or {}).get("status_code"),
                "retry_after_seconds": (state.last_model_action or {}).get("retry_after_seconds"),
                "transient_kind": (state.last_model_action or {}).get("transient_kind"),
            },
            hard_blocker_reason=finish_reason if run_status == AutonomyRunStatus.BLOCKED else None,
        )

    def _reset_runtime_state(self, session_key: str) -> RuntimeV2State:
        state = self._get_runtime_state(session_key)
        state.increment_generation()
        state.history = []
        state.pending_artifacts = []
        state.last_uploaded_artifact = None
        state.last_explicit_target = None
        state.last_inferred_action = None
        state.last_inferred_target = None
        state.pending_bundle_summary = None
        state.last_tool_result = None
        state.last_tool_result_turn_id = None
        state.last_verification_result = None
        state.ingress_context = None
        state.clear_last_delivered_evidence_context()
        state.proto_self_version_override = None
        state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
        state.proto_self_context = None
        runtime_loop = self.runtime_v2_loop
        if runtime_loop is not None:
            runtime_loop._states[session_key] = state
        return state

    def _sync_state_into_runtime_v2_loop(self, session_key: str, state: RuntimeV2State):
        runner = self.telegram_runtime_fallback_runner
        if runner is None:
            runner = TelegramRuntimeFallbackRunner()
            self.telegram_runtime_fallback_runner = runner
            self.runtime_v2_fallback_runner = runner
        runtime_loop = runner.attach_state(session_key, state)
        self.runtime_v2_loop = runtime_loop
        return runtime_loop

    def _get_native_loop(self) -> Optional[NativeToolCallingLoop]:
        if not self.use_runtime_v2:
            return None
        if self.native_loop is None:
            self.native_loop = NativeToolCallingLoop()
        return self.native_loop

    def _get_native_openemotion_hooks(self) -> Optional[NativeOpenEmotionHooks]:
        if self.native_openemotion_hooks is None:
            self.native_openemotion_hooks = NativeOpenEmotionHooks()
        return self.native_openemotion_hooks

    def _get_subject_gate(self) -> Optional[MandatorySubjectGate]:
        hooks = self._get_native_openemotion_hooks()
        if self.subject_gate is None or getattr(self.subject_gate, "hooks", None) is not hooks:
            self.subject_gate = MandatorySubjectGate(hooks=hooks)
        return self.subject_gate

    def _build_runtime_v2_subject_turn_id(
        self,
        *,
        prefix: str = "runtime_v2",
        session_key: str,
        ingress_message_id: Optional[int],
        trace_id: Optional[str],
    ) -> str:
        parts = [str(prefix or "runtime_v2"), str(session_key or "unknown")]
        if ingress_message_id is not None:
            parts.append(f"msg{int(ingress_message_id)}")
        if trace_id:
            parts.append(str(trace_id))
        return ":".join(parts)

    async def _ensure_subject_ingress(
        self,
        *,
        update: Update,
        session_key: str,
        state: RuntimeV2State,
        text: str,
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
        turn_prefix: str,
        source: str = "telegram",
    ) -> bool:
        subject_gate = self._get_subject_gate()
        if subject_gate is None:
            logger.error(
                "%s.subject_gate.missing session=%s msg_id=%s trace=%s",
                turn_prefix,
                session_key,
                ingress_message_id,
                trace_id,
            )
            await self._send_reply(update, "subject_gate_failed：主体暂时不可用，这一步已阻断，请稍后重试。")
            return False

        verdict = subject_gate.process_ingress(
            session_id=session_key,
            turn_id=self._build_runtime_v2_subject_turn_id(
                prefix=turn_prefix,
                session_key=session_key,
                ingress_message_id=ingress_message_id,
                trace_id=trace_id,
            ),
            source=source,
            user_input=text,
            state=state,
            evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
        )
        if verdict.ok:
            return True

        logger.warning(
            "%s.subject_gate.ingress.blocked session=%s msg_id=%s trace=%s reason=%s",
            turn_prefix,
            session_key,
            ingress_message_id,
            trace_id,
            verdict.reason,
        )
        await self._send_reply(
            update,
            verdict.reply_text or "subject_gate_failed：主体暂时不可用，这一步已阻断，请稍后重试。",
        )
        return False

    async def _ensure_runtime_v2_subject_ingress(
        self,
        *,
        update: Update,
        session_key: str,
        state: RuntimeV2State,
        text: str,
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
    ) -> bool:
        return await self._ensure_subject_ingress(
            update=update,
            session_key=session_key,
            state=state,
            text=text,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
            turn_prefix="runtime_v2",
        )

    def _finalize_native_openemotion_turn(
        self,
        *,
        session_key: str,
        turn_id: str,
        state: RuntimeV2State,
        turn_result: TelegramTurnResult,
        native_hooks: Optional[NativeOpenEmotionHooks],
    ) -> None:
        if native_hooks is None or not native_hooks.enabled:
            return
        collector = get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None
        try:
            native_hooks.process_finalized_result(
                session_id=session_key,
                turn_id=turn_id,
                result=turn_result,
                state=state,
                evidence_collector=collector,
            )
        except Exception as e:
            logger.exception("native_openemotion.finalized_result.failed session=%s err=%s", session_key, e)
        try:
            native_hooks.process_idle_check(
                session_id=session_key,
                turn_id=turn_id,
                state=state,
                evidence_collector=collector,
            )
        except Exception as e:
            logger.exception("native_openemotion.idle_check.failed session=%s err=%s", session_key, e)

    def is_allowed(self, chat_id: int) -> bool:
        """Check if chat ID is allowed to interact with bot."""
        if self.allowed_chat_ids is None:
            return True
        return chat_id in self.allowed_chat_ids

    def _start_evidence_capture_for_update(
        self,
        update: Update,
        *,
        chat_id: int,
        user_id: int,
        username: Optional[str],
        text: str,
    ) -> None:
        if not _EVIDENCE_COLLECTOR_AVAILABLE:
            return
        try:
            collector = get_evidence_collector()
            update_id = getattr(update, "update_id", None)
            update_dict = update.to_dict() if hasattr(update, "to_dict") else {
                "update_id": update_id,
                "message": {
                    "message_id": update.message.message_id if update.message else None,
                    "date": update.message.date.isoformat() if update.message and update.message.date else None,
                    "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": user_id, "username": username},
                    "text": text,
                },
            }
            collector.start_sample(update_dict)
            logger.info(f"[E4-EVIDENCE] Started evidence capture for update_id={update_id}")
        except Exception as e:
            logger.warning(f"[E4-EVIDENCE] Failed to start capture: {e}")

    async def _capture_command_ingress(
        self,
        *,
        update: Update,
        session_key: str,
        text: str,
    ) -> bool:
        state = self._get_runtime_state(session_key)
        ingress_message_id = update.message.message_id if update.message else None
        return await self._ensure_subject_ingress(
            update=update,
            session_key=session_key,
            state=state,
            text=text,
            trace_id=None,
            ingress_message_id=ingress_message_id,
            turn_prefix="command",
        )

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Telegram commands."""
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else 0
        username = update.effective_user.username if update.effective_user else None

        # Check if chat is allowed
        if not self.is_allowed(chat_id):
            logger.warning(f"Unauthorized chat attempt: {chat_id}")
            await update.message.reply_text(
                "⚠️ You are not authorized to use this bot."
            )
            return

        # Parse command
        text = update.message.text
        command, args = self.router.parse_command(text)
        session_key = self._resolve_session_key(update, chat_id, user_id)
        self._remember_session_transport_binding(session_key, chat_id)

        self._start_evidence_capture_for_update(
            update,
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            text=text,
        )
        if not await self._capture_command_ingress(
            update=update,
            session_key=session_key,
            text=text,
        ):
            return

        logger.info(f"Command received: /{command} from user {username or user_id}")

        if command == "context":
            result = self._handle_context_command(update, args, chat_id, user_id, username)
            await self._send_result(update, result)
            return
        if command == "prompt":
            result = self._handle_prompt_command(args)
            await self._send_result(update, result)
            return
        if command == "proto":
            result = self._handle_proto_command(update, args, chat_id, user_id)
            await self._send_result(update, result)
            return
        if command in {"new", "reset"}:
            result = self._handle_session_reset_command(update, command, chat_id, user_id)
            await self._send_result(update, result)
            return
        if command == "status":
            result = self._handle_runtime_status_command(update, chat_id, user_id)
            await self._send_result(update, result)
            return
        if command in {"replace", "append", "cancel"}:
            await self._handle_task_conflict_command(update, command, chat_id, user_id, username)
            return

        # Metrics: Record message received (Phase: PRODUCTION_INTEGRATION)
        # Feature Flag: runtime_metrics_enabled (default: OFF)
        if _METRICS_AVAILABLE:
            record_metric(
                metric_name="telegram_message_received_total",
                metric_type="counter",
                value=1.0,
                labels={"command": command, "chat_id": str(chat_id)},
                module="telegram_bot"
            )

        # Create context
        ctx = CommandContext(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            args=args,
            message_text=text
        )

        # Route command
        result = self.router.route(command, ctx)

        # Metrics: Record response sent (Phase: PRODUCTION_INTEGRATION)
        if _METRICS_AVAILABLE:
            record_metric(
                metric_name="telegram_response_sent_total",
                metric_type="counter",
                value=1.0,
                labels={
                    "command": command,
                    "success": str(result.success),
                    "chat_id": str(chat_id)
                },
                module="telegram_bot"
            )
            # Debug: Print metrics to stdout (goes to egocore.log)
            from system_core import get_metrics_hook
            hook = get_metrics_hook()
            stats = hook.get_stats()
            sample_count = stats.get('adapter_stats', {}).get('buffer', {}).get('size', 0)
            print(f"[METRICS] Samples collected: {sample_count}", flush=True)

        # Send response
        await self._send_result(update, result)

    def _handle_prompt_command(self, args: str) -> CommandResult:
        tokens = [t for t in (args or "").strip().split() if t]
        subcommand = (tokens[0].lower() if tokens else "list")
        prompt_files = RuntimeV2PromptFiles()
        bundle = prompt_files.load()

        if subcommand in {"list", "ls"}:
            lines = [
                "*Prompt Files*",
                f"- root: `{bundle.root}`",
                f"- loaded: `{', '.join(bundle.loaded_names) if bundle.loaded_names else '-'}`",
            ]
            return CommandResult(success=True, message="\n".join(lines), data={"root": bundle.root, "loaded": bundle.loaded_names})

        if subcommand == "reload":
            reloaded = prompt_files.reload()
            lines = [
                "*Prompt Files Reloaded*",
                f"- root: `{reloaded.root}`",
                f"- loaded: `{', '.join(reloaded.loaded_names) if reloaded.loaded_names else '-'}`",
            ]
            return CommandResult(success=True, message="\n".join(lines), data={"root": reloaded.root, "loaded": reloaded.loaded_names, "reloaded": True})

        if subcommand == "show":
            if len(tokens) < 2:
                return CommandResult(success=False, message="用法: /prompt show AGENT.md")
            name = tokens[1]
            content = prompt_files.read_file(name)
            if content is None:
                return CommandResult(success=False, message=f"未找到 prompt 文件: {name}")
            preview = content.strip()
            return CommandResult(success=True, message=f"*{name}*\n```\n{preview[:3500]}\n```", data={"name": name, "content": content})

        return CommandResult(success=False, message="用法: /prompt list | /prompt reload | /prompt show AGENT.md")

    def _handle_proto_command(self, update: Update, args: str, chat_id: int, user_id: int) -> CommandResult:
        session_key = self._resolve_session_key(update, chat_id, user_id)
        state = self._get_runtime_state(session_key)
        tokens = [t.lower() for t in (args or "").strip().split() if t]

        if not tokens or tokens[0] == "status":
            override = state.proto_self_version_override or "default(v2)"
            subject_profile = (
                "default(seed_v0_2)"
                if state.proto_self_subject_profile_override == SEED_SUBJECT_PROFILE and state.proto_self_version_override is None
                else state.proto_self_subject_profile_override or "default(core_v2)"
            )
            return CommandResult(
                success=True,
                message=(
                    "*Proto-Self Ingress Mode*\n\n"
                    f"- session: `{session_key}`\n"
                    f"- version_override: `{override}`\n"
                    f"- subject_profile: `{subject_profile}`\n"
                    "- scope: `session-scoped`\n"
                    "- effect: `future runtime_v2 natural-language turns only`\n"
                    "- boundary: `proto_self.v2 uses seed_v0_2 as the default subject profile; /proto seed off explicitly falls back to core_v2`"
                ),
                data={
                    "session_key": session_key,
                    "proto_self_version_override": state.proto_self_version_override,
                    "proto_self_subject_profile_override": state.proto_self_subject_profile_override,
                },
            )

        if tokens[:2] == ["v2", "on"]:
            state.proto_self_version_override = None
            if not state.proto_self_subject_profile_override:
                state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
            return CommandResult(
                success=True,
                message=(
                    "*Proto-Self Ingress Mode Updated*\n\n"
                    f"- session: `{session_key}`\n"
                    "- version_override: `default(v2)`\n"
                    "- subject_profile: `default(seed_v0_2)`\n"
                    "- next_step: `future runtime_v2 natural-language turns stay on the default seed_v0_2 profile inside proto_self.v2`"
                ),
                data={
                    "session_key": session_key,
                    "proto_self_version_override": None,
                    "proto_self_subject_profile_override": state.proto_self_subject_profile_override,
                },
            )

        if tokens[0] in {"off", "clear", "default"} or tokens[:2] == ["v2", "off"]:
            state.proto_self_version_override = "v1"
            state.proto_self_subject_profile_override = None
            return CommandResult(
                success=True,
                message=(
                    "*Proto-Self Ingress Mode Updated*\n\n"
                    f"- session: `{session_key}`\n"
                    "- version_override: `v1`\n"
                    "- subject_profile: `default(core_v2)`\n"
                    "- boundary: `temporary compatibility fallback; default mainline remains v2`"
                ),
                data={
                    "session_key": session_key,
                    "proto_self_version_override": "v1",
                    "proto_self_subject_profile_override": None,
                },
            )

        if tokens[:2] == ["seed", "on"]:
            state.proto_self_version_override = None
            state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
            return CommandResult(
                success=True,
                message=(
                    "*Proto-Self Ingress Mode Updated*\n\n"
                    f"- session: `{session_key}`\n"
                    "- version_override: `default(v2)`\n"
                    "- subject_profile: `default(seed_v0_2)`\n"
                    "- next_step: `future runtime_v2 natural-language turns stay on the default seed_v0_2 profile inside proto_self.v2`"
                ),
                data={
                    "session_key": session_key,
                    "proto_self_version_override": None,
                    "proto_self_subject_profile_override": SEED_SUBJECT_PROFILE,
                },
            )

        if tokens[:2] == ["seed", "off"]:
            state.proto_self_subject_profile_override = None
            return CommandResult(
                success=True,
                message=(
                    "*Proto-Self Ingress Mode Updated*\n\n"
                    f"- session: `{session_key}`\n"
                    f"- version_override: `{state.proto_self_version_override or 'default(v2)'}`\n"
                    "- subject_profile: `default(core_v2)`\n"
                    "- boundary: `seed_v0_2 disabled; this session now uses core_v2 on the proto_self.v2 mainline unless version fallback is set`"
                ),
                data={
                    "session_key": session_key,
                    "proto_self_version_override": state.proto_self_version_override,
                    "proto_self_subject_profile_override": None,
                },
            )

        return CommandResult(
            success=False,
            message="用法: /proto status | /proto v2 on | /proto off | /proto seed on | /proto seed off",
            data={"session_key": session_key},
        )

    def _handle_session_reset_command(self, update: Update, command: str, chat_id: int, user_id: int) -> CommandResult:
        session_key = self._resolve_session_key(update, chat_id, user_id)
        context_store = get_session_context_store()
        context_store.clear_session(session_key)
        if self.autonomy_orchestrator is not None:
            self.autonomy_orchestrator.supersede_session_runs(session_key)
        runtime_loop = self.runtime_v2_loop
        if runtime_loop is not None:
            state = runtime_loop.reset_session(session_key, command=f"/{command}")
            self._runtime_states[session_key] = state
        else:
            state = self._reset_runtime_state(session_key)
            native_hooks = self._get_native_openemotion_hooks()
            runtime = getattr(native_hooks, "runtime", None) if native_hooks else None
            adapter = getattr(runtime, "adapter", None) if runtime else None
            state_store = getattr(adapter, "state_store", None)
            if state_store is not None:
                try:
                    state_store.record_session_reset(
                        session_id=session_key,
                        thread_id=session_key,
                        source="telegram_command",
                        command=f"/{command}",
                        generation_id=state.generation_id,
                    )
                except Exception as e:
                    logger.warning(f"[PSK-RESET] Failed to record command reset for {session_key}: {e}")
        self._latest_message_id_by_session.pop(session_key, None)
        verb = "started fresh" if command == "new" else "reset"
        return CommandResult(
            success=True,
            message=(
                "🆕 *Session Reset*\n\n"
                f"- session_key: `{session_key}`\n"
                f"- action: `{verb}`\n"
                "- context: cleared\n"
                "- runtime_state: reset"
            ),
            data={"session_key": session_key, "action": command, "reset": True},
        )

    async def _handle_task_conflict_command(
        self,
        update: Update,
        command: str,
        chat_id: int,
        user_id: int,
        username: Optional[str],
    ) -> None:
        session_key = self._resolve_session_key(update, chat_id, user_id)
        state = self._get_runtime_state(session_key)
        ingress_message_id = update.message.message_id if update.message else None
        incoming_text = await self._apply_pending_task_conflict_resolution(
            state=state,
            resolution=command,
            trace_id=None,
            ingress_message_id=ingress_message_id,
            session_key=session_key,
        )
        if incoming_text is None:
            await self._send_result(update, CommandResult(success=False, message=self._build_invalid_task_conflict_reply()))
            return
        if command == "replace":
            async with self._typing_indicator(update):
                await self._handle_with_runtime_v2(
                    update,
                    incoming_text,
                    chat_id,
                    user_id,
                    username,
                )
            return
        if command == "append":
            await self._send_result(update, CommandResult(success=True, message="已把新任务追加到当前任务队列。当前任务恢复后会按顺序继续。"))
            return
        await self._send_result(update, CommandResult(success=True, message="已取消这次新任务，保持当前任务不变。"))

    def _handle_runtime_status_command(self, update: Update, chat_id: int, user_id: int) -> CommandResult:
        session_key = self._resolve_session_key(update, chat_id, user_id)
        context_store = get_session_context_store()
        recent_turns = context_store.get_recent_turns(session_key, limit=20)
        state = self._get_runtime_state(session_key) if self.use_runtime_v2 else None
        prompt_bundle = RuntimeV2PromptFiles().load() if self.use_runtime_v2 else None

        # Real token data from state
        if state:
            prompt_tokens = state.total_prompt_tokens
            completion_tokens = state.total_completion_tokens
            total_tokens = state.get_total_tokens()
            llm_calls = state.llm_call_count
            compactions = state.compaction_count
        else:
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            llm_calls = 0
            compactions = 0

        # Context usage = prompt_tokens sent to LLM
        context_k = max(1, round(prompt_tokens / 1000))
        context_pct = min(99, round((prompt_tokens / 200000) * 100)) if prompt_tokens else 0
        history_file = f"{session_key.replace(':', '_')}.jsonl"
        updated_text = "just now"

        # Format tokens with k suffix
        def format_tokens(t: int) -> str:
            if t >= 1000:
                return f"{round(t / 1000)}k"
            return str(t)

        prompt_k = format_tokens(prompt_tokens)
        completion_k = format_tokens(completion_tokens)

        try:
            config = get_config()
            chat_cfg = config.get_llm_config_for_use_case("chat")
            chat_provider = str(chat_cfg.get("provider") or config.llm.get("default_provider") or "unknown")
            chat_model = str(chat_cfg.get("model") or config.llm.get("default_model") or "unknown")
        except ConfigError:
            chat_provider = "unknown"
            chat_model = "unknown"

        # Rough cost estimate retained as a coarse status hint.
        cost = (prompt_tokens * 0.000001 + completion_tokens * 0.000002)

        lines = [
            "🦞 *EgoCore Runtime*",
            f"🧠 Model: `{chat_provider}/{chat_model}` · 🔑 `api-key` (llm.yaml)",
            f"🧮 Tokens: `{prompt_k}` in / `{completion_k}` out · 💵 Cost: `${cost:.4f}`",
            f"📚 Context: `{context_k}k/200k ({context_pct}%)` · 🧹 Compactions: `{compactions}`",
            f"Session ID: `{session_key}`",
            f"📜 History: `available` · file: `{history_file}`",
            f"🧵 Session: `{session_key}` • updated {updated_text}",
            "⚙️ Runtime: `native_loop` primary · `runtime_v2` fallback",
            f"🪢 Queue: `collect` (depth 0) · LLM calls: `{llm_calls}`",
        ]

        if state is not None:
            lines.extend([
                "",
                "*Runtime v2*",
                f"- task_status: `{state.task_status}`",
                f"- task_id: `{state.task_id or '-'}`",
                f"- current_goal: `{(state.current_goal or '-')[:120]}`",
                f"- current_step: `{(state.current_step or '-')[:120]}`",
                f"- history_items: `{len(state.history)}`",
            ])
            # Pending artifacts
            pending_count = len(state.pending_artifacts) if hasattr(state, 'pending_artifacts') else 0
            last_artifact = state.last_uploaded_artifact if hasattr(state, 'last_uploaded_artifact') else None
            lines.extend([
                f"- pending_artifacts: `{pending_count}`",
                f"- last_uploaded: `{last_artifact.get('filename', '-') if last_artifact else '-'}`",
            ])
        if prompt_bundle is not None:
            lines.extend([
                "",
                "*Prompts*",
                f"- root: `{prompt_bundle.root}`",
                f"- loaded: `{', '.join(prompt_bundle.loaded_names) if prompt_bundle.loaded_names else '-'}`",
            ])

        return CommandResult(success=True, message="\n".join(lines), data={"session_key": session_key, "task_status": state.task_status if state else None})

    def _handle_context_command(self, update: Update, args: str, chat_id: int, user_id: int, username: Optional[str]) -> CommandResult:
        subcommand = (args or "").strip().lower() or "list"
        if subcommand not in {"list", "ls"}:
            return CommandResult(success=False, message="用法: /context list")

        session_key = self._resolve_session_key(update, chat_id, user_id)
        context_store = get_session_context_store()
        recent_turns = context_store.get_recent_turns(session_key, limit=10)
        turn_index = context_store.get_turn_index(session_key)

        lines = [
            "*Loaded Context*",
            f"- session_key: `{session_key}`",
            f"- user: `{username or user_id}`",
            f"- recent_turns: `{len(recent_turns)}`",
            f"- turn_index: `{turn_index}`",
        ]

        if self.use_runtime_v2:
            state = self._get_runtime_state(session_key)
            prompt_bundle = RuntimeV2PromptFiles().load()
            lines.extend([
                "",
                "*Runtime State*",
                f"- task_status: `{state.task_status}`",
                f"- task_id: `{state.task_id or '-'} `",
                f"- current_goal: `{(state.current_goal or '-')[:120]}`",
                f"- current_step: `{(state.current_step or '-')[:120]}`",
                f"- waiting_for_user_input: `{state.waiting_for_user_input}`",
                f"- history_items: `{len(state.history)}`",
                f"- last_challenge_turn: `{(state.last_challenge_turn or '-')[:80]}`",
                f"- prompt_root: `{prompt_bundle.root}`",
                f"- loaded_prompt_files: `{', '.join(prompt_bundle.loaded_names) if prompt_bundle.loaded_names else '-'}`",
            ])

        if recent_turns:
            lines.extend(["", "*Recent Turns*"])
            for turn in recent_turns[-5:]:
                role = turn.get("role", "?")
                content = str(turn.get("content", "")).replace("`", "'")
                lines.append(f"- {role}: `{content[:120]}`")

        return CommandResult(success=True, message="\n".join(lines), data={"session_key": session_key, "recent_turns": recent_turns})

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle natural language messages."""
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else 0
        username = update.effective_user.username if update.effective_user else None

        # Check if chat is allowed
        if not self.is_allowed(chat_id):
            logger.warning(f"Unauthorized chat attempt: {chat_id}")
            return

        text = update.message.text

        # E4 Evidence: Start capturing for real Telegram messages
        if _EVIDENCE_COLLECTOR_AVAILABLE:
            try:
                collector = get_evidence_collector()
                # Convert Update to dict for capture
                update_dict = update.to_dict() if hasattr(update, 'to_dict') else {
                    "update_id": update.update_id,
                    "message": {
                        "message_id": update.message.message_id,
                        "date": update.message.date.isoformat() if update.message.date else None,
                        "chat": {"id": chat_id, "type": "private"},
                        "from": {"id": user_id, "username": username},
                        "text": text,
                    }
                }
                collector.start_sample(update_dict)
                logger.info(f"[E4-EVIDENCE] Started evidence capture for update_id={update.update_id}")
            except Exception as e:
                logger.warning(f"[E4-EVIDENCE] Failed to start capture: {e}")

        # Skip only known commands (avoid treating file paths like /home/... as commands)
        if text.strip().startswith('/'):
            cmd, _args = self.router.parse_command(text)
            known = getattr(self, "_known_commands", set())
            if cmd in known:
                return

        trace_id = uuid.uuid4().hex[:10]
        msg_id = update.message.message_id if update.message else None
        session_key = self._resolve_session_key(update, chat_id, user_id)
        self._remember_session_transport_binding(session_key, chat_id)
        if msg_id is not None:
            prev = self._latest_message_id_by_session.get(session_key)
            self._latest_message_id_by_session[session_key] = max(int(msg_id), int(prev)) if prev is not None else int(msg_id)
        logger.info(f"[trace={trace_id}] ingress message_id={msg_id} session={session_key} user={username or user_id} text={text[:80]}")

        # 检查是否是超长消息（>8KB），如果是则走 ingestion 流程
        if self.use_runtime_v2 and self._is_long_message(text):
            logger.info(f"[trace={trace_id}] long message detected ({len(text)} chars), routing through ingestion")
            async with self._typing_indicator(update):
                await self._handle_long_message_with_ingestion(
                    update, text, chat_id, user_id, username, trace_id, msg_id, session_key
                )
            return

        if self.use_runtime_v2:
            async with self._typing_indicator(update):
                await self._handle_with_runtime_v2(update, text, chat_id, user_id, username, trace_id=trace_id)
        elif self.use_new_runtime:
            if not self._legacy_runtime_notice_logged:
                logger.warning("TelegramBot compatibility path in use: _handle_with_new_runtime is legacy/non-mainline; prefer Runtime v2")
                self._legacy_runtime_notice_logged = True
            async with self._typing_indicator(update):
                await self._handle_with_new_runtime(update, text, chat_id, user_id, username, trace_id=trace_id)
        else:
            if not self._legacy_runtime_notice_logged:
                logger.warning("TelegramBot legacy router path in use: _handle_with_legacy_router is compatibility-only; prefer Runtime v2")
                self._legacy_runtime_notice_logged = True
            await self._handle_with_legacy_router(update, text, chat_id, user_id, username)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle Telegram document messages (file attachments).

        支持的文件类型：.txt, .md, .log, .json, .yaml, .yml, .csv
        流程：下载 → 落盘 → 处理 → 注入 Runtime v2
        """
        if not update.message or not update.message.document:
            return

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else 0
        username = update.effective_user.username if update.effective_user else None

        # Check if chat is allowed
        if not self.is_allowed(chat_id):
            logger.warning(f"Unauthorized chat attempt: {chat_id}")
            return

        document = update.message.document
        session_key = self._resolve_session_key(update, chat_id, user_id)
        self._remember_session_transport_binding(session_key, chat_id)
        trace_id = uuid.uuid4().hex[:10]
        msg_id = update.message.message_id

        logger.info(
            f"[trace={trace_id}] document received: "
            f"filename={document.file_name} mime={document.mime_type} "
            f"size={document.file_size} session={session_key}"
        )

        # 获取 ingestion manager
        if self._ingestion_manager is None:
            self._ingestion_manager = get_ingestion_manager()

        # 检查是否支持
        if not self._ingestion_manager.is_supported_document(
            document.mime_type,
            document.file_name,
        ):
            state = self._get_runtime_state(session_key)
            ingress_text = f"[用户发送了文件: {document.file_name or 'unnamed'}]"
            if not await self._ensure_subject_ingress(
                update=update,
                session_key=session_key,
                state=state,
                text=ingress_text,
                trace_id=trace_id,
                ingress_message_id=msg_id,
                turn_prefix="document",
            ):
                return
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text=(
                    f"收到文件「{document.file_name or 'unnamed'}」，"
                    f"但暂不支持此类型（{document.mime_type or 'unknown'}）。"
                    f"\n\n支持的类型：txt, md, log, json, yaml, csv"
                ),
                status="document_unsupported_type",
                delivery_kind="final",
                authority_source="host_document_ingestion",
                reply_authority="host_document",
                metadata={"conversation_act": "document_unsupported_type"},
            )
            return

        async with self._typing_indicator(update):
            state = self._get_runtime_state(session_key)
            ingress_text = f"[用户发送了文件: {document.file_name or 'unnamed'}]"
            # 下载文件
            try:
                file = await context.bot.get_file(document.file_id)
                content = await file.download_as_bytearray()
                content = bytes(content)
            except Exception as e:
                logger.error(f"[trace={trace_id}] failed to download file: {e}")
                if not await self._ensure_subject_ingress(
                    update=update,
                    session_key=session_key,
                    state=state,
                    text=ingress_text,
                    trace_id=trace_id,
                    ingress_message_id=msg_id,
                    turn_prefix="document",
                ):
                    return
                await self._send_host_owned_reply(
                    update,
                    state=state,
                    reply_text=f"文件下载失败：{e}",
                    status="document_download_failed",
                    delivery_kind="final",
                    authority_source="host_document_ingestion",
                    reply_authority="host_document",
                    metadata={"conversation_act": "document_download_failed"},
                )
                return

            # 构建文档信息
            doc_info = TelegramDocumentInfo(
                file_id=document.file_id,
                file_unique_id=document.file_unique_id,
                filename=document.file_name,
                mime_type=document.mime_type or "text/plain",
                file_size=document.file_size,
                message_id=msg_id,
                caption=update.message.caption,
            )

            result = await self._ingestion_manager.ingest_telegram_document(
                document_info=doc_info,
                content=content,
                session_key=session_key,
            )

            if not result.success:
                logger.error(f"[trace={trace_id}] ingestion failed: {result.error}")
                if not await self._ensure_subject_ingress(
                    update=update,
                    session_key=session_key,
                    state=state,
                    text=ingress_text,
                    trace_id=trace_id,
                    ingress_message_id=msg_id,
                    turn_prefix="document",
                ):
                    return
                await self._send_host_owned_reply(
                    update,
                    state=state,
                    reply_text=f"文件处理失败：{result.error}",
                    status="document_ingestion_failed",
                    delivery_kind="final",
                    authority_source="host_document_ingestion",
                    reply_authority="host_document",
                    metadata={"conversation_act": "document_ingestion_failed"},
                )
                return

            ingested = result.ingested_input
            logger.info(
                f"[trace={trace_id}] document ingested: "
                f"artifact_id={ingested.attachments[0].artifact_id if ingested.attachments else 'none'}"
            )

            if self.use_runtime_v2:
                artifact_id = None
                if ingested._compacted_artifact:
                    artifact_id = ingested._compacted_artifact.artifact_id
                elif ingested.artifact_refs:
                    artifact_id = ingested.artifact_refs[0]
                elif ingested.attachments:
                    artifact_id = ingested.attachments[0].artifact_id

                session_key = self._resolve_session_key(update, chat_id, user_id)
                state = self._get_runtime_state(session_key)
                if artifact_id:
                    state.add_pending_artifact(
                        artifact_id=artifact_id,
                        filename=document.file_name,
                        artifact_ref=artifact_id,
                    )

                prompt_context = ingested.to_prompt_context()
                user_input = ingested.user_text or f"[用户发送了文件: {document.file_name}]"

                await self._handle_with_runtime_v2(
                    update=update,
                    text=user_input,
                    chat_id=chat_id,
                    user_id=user_id,
                    username=username,
                    trace_id=trace_id,
                    extra_context=prompt_context,
                )
            else:
                summary = ingested.summary or "文件已处理完成。"
                reply = f"文件「{document.file_name}」已处理。\n\n{summary[:500]}"
                if len(summary) > 500:
                    reply += "\n... (摘要已截断)"
                if not await self._ensure_subject_ingress(
                    update=update,
                    session_key=session_key,
                    state=state,
                    text=ingress_text,
                    trace_id=trace_id,
                    ingress_message_id=msg_id,
                    turn_prefix="document",
                ):
                    return
                await self._send_host_owned_reply(
                    update,
                    state=state,
                    reply_text=reply,
                    status="document_processed",
                    delivery_kind="final",
                    authority_source="host_document_ingestion",
                    reply_authority="host_document",
                    metadata={"conversation_act": "document_processed"},
                )

    def _resolve_session_key(self, update: Update, chat_id: int, user_id: int) -> str:
        """Resolve canonical session key for Telegram ingress."""
        chat_type = update.effective_chat.type if update.effective_chat else "private"
        if chat_type == "private":
            return f"telegram:dm:{user_id}"
        return f"telegram:group:{chat_id}"

    def _is_stale_reply(self, session_key: str, ingress_message_id: Optional[int]) -> bool:
        """Check whether current result is stale vs latest ingress in same session."""
        if ingress_message_id is None:
            return False
        latest = self._latest_message_id_by_session.get(session_key)
        if latest is None:
            return False
        return int(ingress_message_id) < int(latest)

    def _build_delivery_identity(
        self,
        session_key: str,
        ingress_message_id: Optional[int],
        reply_text: str,
        request_id: Optional[str] = None,
        delivery_kind: str = "final",
    ) -> DeliveryIdentity:
        return DeliveryIdentity.build(
            session_key=session_key,
            reply_text=reply_text,
            delivery_kind=delivery_kind,
            request_id=request_id,
            source_ingress_message_id=str(ingress_message_id) if ingress_message_id is not None else None,
        )

    def _is_duplicate_outbound(
        self,
        session_key: str,
        ingress_message_id: Optional[int],
        reply_text: str,
        request_id: Optional[str] = None,
        delivery_kind: str = "final",
    ) -> bool:
        identity = self._build_delivery_identity(
            session_key=session_key,
            ingress_message_id=ingress_message_id,
            reply_text=reply_text,
            request_id=request_id,
            delivery_kind=delivery_kind,
        )
        return self._delivery_dedupe_policy.should_suppress(identity)

    def _is_long_message(self, text: str) -> bool:
        """检查是否是超长消息（>8KB 或 >8000 字符）"""
        # 与 ingestion manager 的阈值保持一致
        return len(text) > 8000

    async def _handle_long_message_with_ingestion(
        self,
        update: Update,
        text: str,
        chat_id: int,
        user_id: int,
        username: Optional[str],
        trace_id: Optional[str],
        msg_id: Optional[int],
        session_key: str,
    ) -> None:
        """
        通过 ingestion 层处理超长普通消息

        流程：
        1. 使用 ingestion manager 将长文本转为 artifact
        2. 生成摘要和引用
        3. 注入 Runtime v2（与普通文件处理一致）
        """
        try:
            # 获取 ingestion manager
            if self._ingestion_manager is None:
                self._ingestion_manager = get_ingestion_manager()

            # 摄入长消息
            result = await self._ingestion_manager.ingest_long_message(
                text=text,
                session_key=session_key,
                message_id=str(msg_id) if msg_id else "unknown",
            )

            if not result.success:
                logger.error(f"[trace={trace_id}] long message ingestion failed: {result.error}")
                # 降级：直接处理原始文本（截断）
                await self._handle_with_runtime_v2(
                    update=update,
                    text=text[:4000] + "\n... [消息过长，已截断]",
                    chat_id=chat_id,
                    user_id=user_id,
                    username=username,
                    trace_id=trace_id,
                )
                return

            ingested = result.ingested_input

            # 获取 artifact 信息
            artifact_id = None
            if ingested._compacted_artifact:
                artifact_id = ingested._compacted_artifact.artifact_id
            elif ingested.artifact_refs:
                artifact_id = ingested.artifact_refs[0]

            # 更新 state 的 pending_artifacts
            state = self._get_runtime_state(session_key)
            if artifact_id:
                state.add_pending_artifact(
                    artifact_id=artifact_id,
                    filename=f"message_{msg_id}.txt",
                    artifact_ref=artifact_id,
                )

            # 构建 prompt context（使用 compaction 层的 capsule）
            prompt_context = ingested.to_prompt_context()

            # 用户输入只保留前部，避免重复
            user_input = f"[用户发送了超长消息，共 {len(text)} 字符]"
            if ingested.user_text:
                user_input += f"\n开头: {ingested.user_text[:200]}..."

            logger.info(
                f"[trace={trace_id}] long message ingested: artifact_id={artifact_id}, "
                f"entering runtime v2"
            )

            await self._handle_with_runtime_v2(
                update=update,
                text=user_input,
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                trace_id=trace_id,
                extra_context=prompt_context,
            )

        except Exception as e:
            logger.exception(f"[trace={trace_id}] failed to handle long message: {e}")
            # 降级：直接处理（截断）
            await self._handle_with_runtime_v2(
                update=update,
                text=text[:4000] + "\n... [处理异常，已截断]",
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                trace_id=trace_id,
            )

    async def _handle_with_runtime_v2(
        self,
        update: Update,
        text: str,
        chat_id: int,
        user_id: int,
        username: Optional[str],
        trace_id: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> None:
        session_key = self._resolve_session_key(update, chat_id, user_id)
        state = self._get_runtime_state(session_key)
        ingress_message_id = update.message.message_id if update.message else None

        normalized_turn = normalize_user_turn(text)

        # 记录 ingress 信息
        if ingress_message_id is not None:
            prev = self._latest_message_id_by_session.get(session_key)
            self._latest_message_id_by_session[session_key] = max(int(ingress_message_id), int(prev)) if prev is not None else int(ingress_message_id)

        # 日志点1: ingress 记录
        logger.info(
            "runtime_v2.ingress trace=%s session=%s msg_id=%s latest_msg_id=%s user_input=%s",
            trace_id, session_key, ingress_message_id,
            self._latest_message_id_by_session.get(session_key),
            text[:80].replace("\n", " ") if text else None
        )
        await self._publish_phase1_event(
            session_key=session_key,
            kind="telegram_ingress",
            trace_id=trace_id,
            message_id=ingress_message_id,
            payload={
                "text_preview": text[:300],
                "chat_id": chat_id,
                "user_id": user_id,
                "username": username,
            },
        )

        raw_event = update.to_dict() if hasattr(update, "to_dict") else {
            "update_id": getattr(update, "update_id", None),
            "message": {
                "message_id": ingress_message_id,
                "chat": {"id": chat_id, "type": getattr(getattr(update, "effective_chat", None), "type", None)},
                "from": {"id": user_id, "username": username},
                "text": text,
            },
        }
        unified_ingress = await build_unified_ingress(
            build_telegram_unified_request(
                session_key=session_key,
                text=text,
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                message_id=ingress_message_id,
                source_kind="telegram_real",
                raw_event=raw_event,
                extra_context=extra_context,
            ),
            state,
            bridge=self.telegram_runtime_bridge,
            llm_client=self._get_semantic_parse_client(),
        )
        text = unified_ingress.request.effective_user_input
        ingress = unified_ingress.semantic_decision
        state.ingress_context = dict(unified_ingress.ingress_context or {})
        if state.proto_self_version_override:
            state.ingress_context = dict(state.ingress_context or {})
            state.ingress_context["proto_self_version"] = state.proto_self_version_override
            state.ingress_context["proto_self_version_source"] = "telegram_session_override"
        if state.proto_self_subject_profile_override:
            state.ingress_context = dict(state.ingress_context or {})
            state.ingress_context["proto_self_subject_profile"] = state.proto_self_subject_profile_override
            state.ingress_context["proto_self_subject_profile_source"] = "telegram_session_override"
        self._sync_pending_result_continuation_from_ingress(state, user_text=text)
        if not await self._ensure_runtime_v2_subject_ingress(
            update=update,
            session_key=session_key,
            state=state,
            text=text,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
        ):
            return

        if state.get_pending_task_conflict() is not None:
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text=self._build_task_conflict_reply(state),
                status="task_conflict_pending",
                delivery_kind="final",
                authority_source="host_pre_runtime",
                reply_authority="host_task_conflict",
                metadata={"conversation_act": "task_conflict"},
            )
            return

        followup_reply = self._build_recent_read_followup_reply(state, text)
        if followup_reply is not None:
            snapshot = getattr(state, "last_delivered_evidence_context", None) or getattr(state, "last_evidence_read_result", None)
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text=followup_reply,
                status="evidence_followup",
                delivery_kind="final",
                authority_source="response_contract.response_plan",
                reply_authority="host_evidence",
                metadata={
                    "conversation_act": "evidence_followup",
                    "evidence_payload": dict(snapshot or {}),
                    "evidence_binding_source_turn": (snapshot or {}).get("source_turn_id"),
                },
            )
            state.clear_last_delivered_evidence_context()
            return
        if normalized_turn.probe_key not in READ_LIST_FOLLOWUP_PROBE_KEYS:
            state.clear_last_delivered_evidence_context()

        pre_runtime = unified_ingress.pre_runtime_action
        runtime_action = getattr(ingress, "_runtime_action", None)
        logger.info("runtime_v2.turn.start session=%s text=%r ingress=%s parser_source=%s",
                    session_key, text[:200], ingress,
                    ingress._parsed_intent_graph.parser_source if ingress._parsed_intent_graph else "none")

        if pre_runtime.remember_challenge_turn:
            state.last_challenge_turn = text

        if self._should_override_stale_task_with_explicit_target(state, ingress):
            state.reset_active_task_context()

        if await self._maybe_handle_runtime_v2_pre_runtime(update, state, pre_runtime):
            await self._publish_phase1_event(
                session_key=session_key,
                kind="telegram_early_return",
                trace_id=trace_id,
                message_id=ingress_message_id,
                payload={
                    "task_status": state.task_status,
                    "waiting_for_user_input": state.waiting_for_user_input,
                    "direct_reply_text": getattr(pre_runtime, "direct_reply_text", None),
                    "waiting_input_text": getattr(pre_runtime, "waiting_input_text", None),
                },
            )
            logger.info("runtime_v2.turn.early_return session=%s reason=pre_runtime busy_notice=%r", session_key, pre_runtime.busy_notice_text)
            return

        self._activate_pending_restore_observation(state)

        if runtime_action == "execute_task":
            self._mark_pending_result_continuation_running_if_needed(state)
            if await self._maybe_create_task_conflict(
                update=update,
                state=state,
                ingress=ingress,
                session_key=session_key,
                text=text,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            ):
                return
            self._prepare_run_items_for_new_task(text, state)

        if runtime_action == "execute_task" and self.autonomy_orchestrator is not None:
            await self._run_with_autonomy(
                update=update,
                session_key=session_key,
                text=text,
                state=state,
                ingress=ingress,
                ack_text=pre_runtime.ack_text,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
                chat_id=chat_id,
                user_id=user_id,
                username=username,
            )
            return

        result = await self._run_primary_turn(
            update=update,
            session_key=session_key,
            text=text,
            state=state,
            ingress=ingress,
            ack_text=pre_runtime.ack_text,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
            chat_id=chat_id,
        )
        logger.info("runtime_v2.turn.result session=%s status=%s reply=%r step=%r tool=%r verification=%r", session_key, result.status, result.reply_text[:200], state.current_step, state.last_tool_result, state.last_verification_result)
        await self._publish_phase1_event(
            session_key=session_key,
            kind="runtime_v2_result",
            trace_id=trace_id,
            message_id=ingress_message_id,
            payload={
                "status": result.status,
                "reply_text": result.reply_text[:1000] if result.reply_text else "",
                "current_step": state.current_step,
                "last_tool_result": state.last_tool_result or {},
                "last_verification_result": state.last_verification_result or {},
            },
        )
        await self._deliver_runtime_v2_result(
            update=update,
            state=state,
            result=result,
            is_challenge_turn=ingress.is_challenge_turn,
            ingress_message_id=ingress_message_id,
            trace_id=trace_id,
        )

    async def _maybe_handle_runtime_v2_pre_runtime(self, update: Update, state, pre_runtime) -> bool:
        if not pre_runtime.should_return_early:
            return False

        if getattr(pre_runtime, "rule_enforcement", None) and pre_runtime.rule_enforcement.get("kind") == "read_only_preflight":
            state.task_status = "waiting_input"
            state.waiting_for_user_input = True
            waiting_text = await self._build_profile_rule_preflight_reply(state, pre_runtime.rule_enforcement)
            response_plan_metadata = dict(getattr(pre_runtime, "response_plan_metadata", None) or {})
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text=waiting_text,
                status=response_plan_metadata.get("status", "read_only_preflight"),
                delivery_kind=response_plan_metadata.get("delivery_kind", "final"),
                authority_source=response_plan_metadata.get("authority_source", "response_contract.response_plan"),
                reply_authority=response_plan_metadata.get("reply_authority", "host_pre_runtime"),
                metadata={
                    "conversation_act": "read_only_preflight",
                    "rule_enforcement": dict(getattr(pre_runtime, "rule_enforcement", {}) or {}),
                    "matched_rule_ids": response_plan_metadata.get("matched_rule_ids") or [],
                    "enforcement": response_plan_metadata.get("enforcement"),
                },
            )
            return True

        # 文件-only：强制 waiting_input，不进入 runtime
        if getattr(pre_runtime, 'force_waiting_input', False):
            state.task_status = "waiting_input"
            state.waiting_for_user_input = True
            waiting_text = getattr(pre_runtime, 'waiting_input_text', '收到文件，请告诉我你要做什么。')
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text=waiting_text,
                status="force_waiting_input",
                delivery_kind="final",
                authority_source="response_contract.response_plan",
                reply_authority="host_pre_runtime",
                metadata={"conversation_act": "force_waiting_input"},
            )
            return True

        if getattr(pre_runtime, "direct_reply_text", None):
            response_plan_metadata = dict(getattr(pre_runtime, "response_plan_metadata", None) or {})
            await self._send_host_owned_reply(
                update,
                state=state,
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
            )
            return True

        # 不再发送 generic busy notice
        # 如果有 busy_notice_text（来自 pre_runtime），也不再发送
        return True

    async def _run_runtime_v2_turn(
        self,
        update: Update,
        session_key: str,
        text: str,
        state,
        ack_text: Optional[str],
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> TelegramTurnResult:
        async def emit_runtime_progress(event: ProgressEvent) -> None:
            if self._should_use_run_item_timeline(state):
                return
            await self._send_autonomy_progress_update(
                state=state,
                phase_key=event.event_type.value,
                text=event.message,
                update=update,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )

        async def emit_run_event(event: RunEvent) -> None:
            if not self._should_use_run_item_timeline(state):
                return
            await self._emit_run_event_message(
                state=state,
                session_key=session_key,
                event=event,
                update=update,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )

        async def run_once() -> TelegramTurnResult:
            if ack_text:
                state.mark_task_started(goal=text)
                try:
                    await self._send_reply(update, ack_text, finalize_evidence=False)
                except Exception:
                    pass

            if self._should_use_run_item_timeline(state):
                await self._ensure_active_run_item_message(
                    state=state,
                    session_key=session_key,
                    update=update,
                    chat_id=chat_id,
                    trace_id=trace_id,
                    ingress_message_id=ingress_message_id,
                )

            # 闭环2：把 pending_artifacts 信息注入 user_input，帮 LLM 知道要执行什么
            enhanced_input = text
            if state.last_uploaded_artifact and not self._has_explicit_path_target(state):
                filename = state.last_uploaded_artifact.get("filename", "未知文件")
                enhanced_input = f"{text}\n\n[目标文件: {filename}]"

            runner = self.telegram_runtime_fallback_runner
            if runner is None:
                runner = TelegramRuntimeFallbackRunner()
                self.telegram_runtime_fallback_runner = runner
                self.runtime_v2_fallback_runner = runner
            self.runtime_v2_loop = runner.get_loop()
            result = await runner.run_turn(
                session_key=session_key,
                user_input=enhanced_input,
                state=state,
                progress_callback=emit_runtime_progress,
                run_event_callback=emit_run_event,
            )
            self.runtime_v2_loop = runner.loop
            return result

        return await run_once()

    async def _continue_runtime_v2_turn(
        self,
        *,
        session_key: str,
        state: RuntimeV2State,
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> TelegramTurnResult:
        async def emit_runtime_progress(event: ProgressEvent) -> None:
            if self._should_use_run_item_timeline(state):
                return
            await self._send_autonomy_progress_update(
                state=state,
                phase_key=event.event_type.value,
                text=event.message,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )

        async def emit_run_event(event: RunEvent) -> None:
            if not self._should_use_run_item_timeline(state):
                return
            await self._emit_run_event_message(
                state=state,
                session_key=session_key,
                event=event,
                update=None,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )

        runner = self.telegram_runtime_fallback_runner
        if runner is None:
            runner = TelegramRuntimeFallbackRunner()
            self.telegram_runtime_fallback_runner = runner
            self.runtime_v2_fallback_runner = runner
        loop = runner.attach_state(session_key, state)
        self.runtime_v2_loop = loop
        if self._should_use_run_item_timeline(state):
            await self._ensure_active_run_item_message(
                state=state,
                session_key=session_key,
                update=None,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )
        result = await loop.continue_turn_typed(
            session_id=session_key,
            state=state,
            progress_callback=emit_runtime_progress,
            run_event_callback=emit_run_event,
        )
        self.runtime_v2_loop = loop
        return runner.adapt_result(result)

    async def _run_with_autonomy(
        self,
        *,
        update: Update,
        session_key: str,
        text: str,
        state: RuntimeV2State,
        ingress,
        ack_text: Optional[str],
        trace_id: Optional[str],
        ingress_message_id: Optional[int],
        chat_id: int,
        user_id: int,
        username: Optional[str],
    ) -> None:
        orchestrator = self.autonomy_orchestrator
        if orchestrator is None:
            raise RuntimeError("autonomy orchestrator unavailable")
        executor_kind = self._select_autonomy_executor_kind(ingress, state)

        async def initial_execute(run: AutonomyRun) -> AutonomySliceOutcome:
            self._sync_autonomy_context(state, run, status=AutonomyRunStatus.RUNNING.value)
            if executor_kind == AutonomyExecutorKind.CONTRACT_EXECUTE:
                result = await self._run_native_loop_turn(
                    update=update,
                    session_key=session_key,
                    text=text,
                    state=state,
                    ack_text=ack_text,
                    chat_id=chat_id,
                    trace_id=trace_id,
                    ingress_message_id=ingress_message_id,
                )
            else:
                result = await self._run_runtime_v2_turn(
                    update=update,
                    session_key=session_key,
                    text=text,
                    state=state,
                    ack_text=ack_text,
                    trace_id=trace_id,
                    ingress_message_id=ingress_message_id,
                    chat_id=chat_id,
                )
            await self._publish_phase1_event(
                session_key=session_key,
                kind="runtime_v2_result",
                trace_id=trace_id,
                message_id=ingress_message_id,
                payload={
                    "status": result.status,
                    "reply_text": result.reply_text[:1000] if result.reply_text else "",
                    "current_step": state.current_step,
                    "last_tool_result": state.last_tool_result or {},
                    "last_verification_result": state.last_verification_result or {},
                    "autonomy_run_id": run.id,
                },
            )
            if self._should_use_run_item_timeline(state):
                await self._emit_newly_verified_run_items(
                    state=state,
                    session_key=session_key,
                    update=update,
                    chat_id=chat_id,
                    trace_id=trace_id,
                    ingress_message_id=ingress_message_id,
                )
            if result.status == "resumable_pause":
                blocked_result = await self._maybe_block_no_progress_run(
                    run=run,
                    state=state,
                    result=result,
                    chat_id=chat_id,
                )
                if blocked_result is not None:
                    return self._build_autonomy_outcome(
                        run=run,
                        state=state,
                        result=blocked_result,
                        default_phase="blocked",
                    )
                sent_progress = 0
                if executor_kind == AutonomyExecutorKind.GENERIC_RUNTIME:
                    sent_progress = await self._deliver_runtime_progress_events(
                        state=state,
                        update=update,
                        trace_id=trace_id,
                        ingress_message_id=ingress_message_id,
                    )
                progress_text = "我继续处理这个任务，做完直接给你结果。"
                if not ack_text and sent_progress == 0 and not self._should_use_run_item_timeline(state):
                    await self._send_autonomy_progress_update(
                        state=state,
                        phase_key="planning_current_slice",
                        text=progress_text,
                        update=update,
                        trace_id=trace_id,
                        ingress_message_id=ingress_message_id,
                    )
                await self._publish_phase1_event(
                    session_key=session_key,
                    kind="autonomy_resumable_pause",
                    trace_id=trace_id,
                    message_id=ingress_message_id,
                    payload={
                        "run_id": run.id,
                        "executor_kind": executor_kind.value,
                        "finish_reason": result.finish_reason,
                    },
                )
                state.task_status = "resumable_pause"
                state.waiting_for_user_input = False
                if self._should_use_run_item_timeline(state):
                    await self._ensure_active_run_item_message(
                        state=state,
                        session_key=session_key,
                        update=update,
                        chat_id=chat_id,
                        trace_id=trace_id,
                        ingress_message_id=ingress_message_id,
                    )
                return self._build_autonomy_outcome(
                    run=run,
                    state=state,
                    result=result,
                    default_phase="planning_current_slice",
                )
            self._clear_no_progress_tracking(run)
            await self._deliver_runtime_v2_result(
                update=update,
                state=state,
                result=result,
                is_challenge_turn=ingress.is_challenge_turn,
                ingress_message_id=ingress_message_id,
                trace_id=trace_id,
            )
            return self._build_autonomy_outcome(
                run=run,
                state=state,
                result=result,
                default_phase="completed",
            )

        run = await orchestrator.submit_ingress(
            surface="telegram",
            session_key=session_key,
            objective=text,
            executor_kind=executor_kind,
            metadata={
                "chat_id": chat_id,
                "user_id": user_id,
                "username": username,
                "trace_id": trace_id,
                "ingress_message_id": ingress_message_id,
            },
            initial_execute=initial_execute,
        )
        self._sync_autonomy_context(state, run)

    async def _resume_telegram_autonomy_run(self, run: AutonomyRun, trigger_source: str) -> AutonomySliceOutcome:
        state = self._restore_runtime_state_snapshot(run.session_key, run.runtime_state_snapshot)
        self._sync_autonomy_context(state, run, status=AutonomyRunStatus.RUNNING.value)
        if trigger_source == "manual":
            self._reset_autonomy_delivery_state(state)
            self._clear_no_progress_tracking(run)
            state.pending_run_events = []
            state.pending_progress_events = []
            if self._should_use_run_item_timeline(state):
                state.resume_active_run_item()
        chat_id = run.metadata.get("chat_id")
        if (
            trigger_source == "driver"
            and run.executor_kind == AutonomyExecutorKind.GENERIC_RUNTIME
            and (run.last_result_summary or {}).get("finish_reason") == "transient_decision_error"
        ):
            retry_limit = self._get_transient_retry_limit(state)
            if run.resume_count >= retry_limit:
                blocked_text = self._build_transient_retry_exhausted_reply()
                state.task_status = "blocked"
                state.waiting_for_user_input = False
                if isinstance(chat_id, int):
                    await self._publish_phase1_event(
                        session_key=run.session_key,
                        kind="telegram_delivery",
                        trace_id=run.metadata.get("trace_id"),
                        message_id=run.metadata.get("ingress_message_id"),
                        payload={
                            "text": blocked_text[:1000],
                            "delivery_kind": "final",
                            "status": "blocked",
                        },
                    )
                    await self._send_chat_message(chat_id, blocked_text, finalize_evidence=True)
                    state.final_sent = True
                blocked_result = TelegramTurnResult(
                    status="blocked",
                    state=state,
                    reply=TelegramTurnReply(
                        reply_text=blocked_text,
                        delivery_kind="final",
                        status="blocked",
                    ),
                    finish_reason=AutonomyStopReason.TRANSIENT_RETRY_BUDGET_EXCEEDED.value,
                    checkpoint_payload=run.checkpoint_payload,
                )
                return self._build_autonomy_outcome(
                    run=run,
                    state=state,
                    result=blocked_result,
                    default_phase="blocked",
                )
            backoff_seconds = self._get_transient_retry_backoff_seconds(state, run)
            if backoff_seconds > 0:
                await asyncio.sleep(backoff_seconds)

        if run.executor_kind == AutonomyExecutorKind.CONTRACT_EXECUTE:
            result = await self._run_native_loop_turn(
                update=None,
                session_key=run.session_key,
                text=state.last_user_turn or run.objective,
                state=state,
                ack_text=None,
                resume_checkpoint=run.checkpoint_payload,
                chat_id=chat_id if isinstance(chat_id, int) else None,
            )
            sent_progress = 0
        else:
            result = await self._continue_runtime_v2_turn(
                session_key=run.session_key,
                state=state,
                trace_id=run.metadata.get("trace_id"),
                ingress_message_id=run.metadata.get("ingress_message_id"),
                chat_id=chat_id if isinstance(chat_id, int) else None,
            )
            sent_progress = await self._deliver_runtime_progress_events(
                state=state,
                chat_id=chat_id if isinstance(chat_id, int) else None,
                trace_id=run.metadata.get("trace_id"),
                ingress_message_id=run.metadata.get("ingress_message_id"),
            )

        run_events_sent = 0
        if self._should_use_run_item_timeline(state):
            run_events_sent = await self._emit_pending_run_events(
                state=state,
                session_key=run.session_key,
                update=None,
                chat_id=chat_id if isinstance(chat_id, int) else None,
                trace_id=run.metadata.get("trace_id"),
                ingress_message_id=run.metadata.get("ingress_message_id"),
            )

        if result.status == "resumable_pause":
            blocked_result = await self._maybe_block_no_progress_run(
                run=run,
                state=state,
                result=result,
                chat_id=chat_id if isinstance(chat_id, int) else None,
            )
            if blocked_result is not None:
                return self._build_autonomy_outcome(
                    run=run,
                    state=state,
                    result=blocked_result,
                    default_phase="blocked",
                )
            if (
                trigger_source == "manual"
                and self._should_use_run_item_timeline(state)
                and getattr(result, "finish_reason", None) == AutonomyStopReason.MAX_STEPS_EXHAUSTED.value
                and sent_progress == 0
                and run_events_sent == 0
            ):
                blocked_text = self._build_manual_resume_stall_reply(state)
                state.task_status = "blocked"
                state.waiting_for_user_input = False
                if isinstance(chat_id, int):
                    await self._publish_phase1_event(
                        session_key=run.session_key,
                        kind="telegram_delivery",
                        trace_id=run.metadata.get("trace_id"),
                        message_id=run.metadata.get("ingress_message_id"),
                        payload={
                            "text": blocked_text[:1000],
                            "delivery_kind": "final",
                            "status": "blocked",
                        },
                    )
                    await self._send_chat_message(chat_id, blocked_text, finalize_evidence=True)
                    state.final_sent = True
                manual_blocked = TelegramTurnResult(
                    status="blocked",
                    state=state,
                    reply=TelegramTurnReply(
                        reply_text=blocked_text,
                        delivery_kind="final",
                        status="blocked",
                    ),
                    finish_reason=AutonomyStopReason.NO_PROGRESS_STALL_DETECTED.value,
                    checkpoint_payload=result.checkpoint_payload,
                )
                return self._build_autonomy_outcome(
                    run=run,
                    state=state,
                    result=manual_blocked,
                    default_phase="blocked",
                )
        else:
            self._clear_no_progress_tracking(run)

        if result.status != "resumable_pause":
            if isinstance(chat_id, int):
                if run.executor_kind == AutonomyExecutorKind.CONTRACT_EXECUTE:
                    if result.reply_text:
                        await self._send_chat_message(chat_id, result.reply_text, finalize_evidence=True)
                        state.final_sent = True
                else:
                    output_verdict = await self._finalize_runtime_delivery_contract(
                        session_key=run.session_key,
                        state=state,
                        result=result,
                        source="runtime_v2_autonomy_resume",
                        trace_id=run.metadata.get("trace_id"),
                        ingress_message_id=run.metadata.get("ingress_message_id"),
                    )
                    delivery = self.telegram_runtime_bridge.plan_delivery(result, state, False)
                    if delivery.should_send and delivery.text:
                        send_result = await self._send_chat_message(chat_id, delivery.text, finalize_evidence=True)
                        if getattr(output_verdict, "evidence_snapshot", None):
                            state.update_last_evidence_read_delivery(
                                delivery_was_chunked=bool((send_result or {}).get("was_chunked"))
                            )
                        if getattr(result, "delivery_kind", "final") == "final" or result.status in {
                            "completed_verified",
                            "completed",
                            "blocked",
                            "failed",
                        }:
                            state.final_sent = True
        else:
            state.task_status = "resumable_pause"
            state.waiting_for_user_input = False
            if self._should_use_run_item_timeline(state):
                await self._ensure_active_run_item_message(
                    state=state,
                    session_key=run.session_key,
                    update=None,
                    chat_id=chat_id if isinstance(chat_id, int) else None,
                    trace_id=run.metadata.get("trace_id"),
                    ingress_message_id=run.metadata.get("ingress_message_id"),
                )
            if (
                isinstance(chat_id, int)
                and run.executor_kind == AutonomyExecutorKind.GENERIC_RUNTIME
                and sent_progress == 0
                and not self._should_use_run_item_timeline(state)
                and trigger_source != "manual"
            ):
                await self._send_autonomy_progress_update(
                    state=state,
                    phase_key="planning_current_slice",
                    text="我继续处理这个任务，做完直接给你结果。",
                    chat_id=chat_id,
                    trace_id=run.metadata.get("trace_id"),
                    ingress_message_id=run.metadata.get("ingress_message_id"),
                )

        return self._build_autonomy_outcome(
            run=run,
            state=state,
            result=result,
            default_phase="planning_current_slice",
        )

    def _should_use_native_loop(self, ingress, state) -> bool:
        if not self.use_runtime_v2:
            return False
        runtime_action = getattr(ingress, "_runtime_action", None)
        interaction_kind = str(((state.ingress_context or {}).get("interaction_kind") or getattr(ingress, "interaction_kind", None) or "")).strip()
        resolved_target = (state.ingress_context or {}).get("resolved_target") or {}
        has_artifact_target = bool(
            str(resolved_target.get("artifact_id") or resolved_target.get("artifact_ref") or "").startswith("artifact://")
        )
        has_explicit_target = bool(resolved_target.get("path")) and resolved_target.get("source") == "explicit_path"
        chat_like_execute = (
            interaction_kind == "chat"
            and runtime_action == "execute_task"
            and (has_artifact_target or has_explicit_target or getattr(ingress, "is_confirm_execution", False))
        )
        if interaction_kind == "chat" and not chat_like_execute:
            return False
        if getattr(ingress, "is_file_only", False) and runtime_action != "execute_task":
            return False
        if state.waiting_for_user_input and not (
            getattr(ingress, "is_confirm_execution", False)
            or (runtime_action == "execute_task" and (has_artifact_target or has_explicit_target))
        ):
            return False
        if runtime_action == "return_runtime_status":
            return False
        if runtime_action != "execute_task":
            return False
        if self.native_loop is not None:
            return True
        if getattr(ingress, "is_confirm_execution", False):
            return True
        if has_artifact_target:
            return True
        if has_explicit_target and state.waiting_for_user_input:
            return True
        return False

    async def _run_primary_turn(
        self,
        update: Update,
        session_key: str,
        text: str,
        state,
        ingress,
        ack_text: Optional[str],
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> TelegramTurnResult:
        if self._should_use_native_loop(ingress, state):
            try:
                await self._publish_phase1_event(
                    session_key=session_key,
                    kind="primary_path_selected",
                    payload={"path": "native_loop", "runtime_action": getattr(ingress, "_runtime_action", None)},
                )
                return await self._run_native_loop_turn(
                    update=update,
                    session_key=session_key,
                    text=text,
                    state=state,
                    ack_text=ack_text,
                    chat_id=chat_id,
                    trace_id=trace_id,
                    ingress_message_id=ingress_message_id,
                )
            except Exception as e:
                logger.exception("native_loop.failed session=%s err=%s; falling back to runtime_v2", session_key, e)
                if self._is_artifact_execute_turn(state, ingress):
                    state.task_status = "blocked"
                    state.waiting_for_user_input = False
                    state.current_step = None
                    blocked_result = TelegramTurnResult(
                        status="blocked",
                        state=state,
                        reply=TelegramTurnReply(
                            reply_text=(
                                "执行任务单时遇到问题，我已经停止旧 fallback 路径，避免卡在 read_artifact。\n\n"
                                f"错误：{str(e).strip() or 'unknown error'}"
                            ),
                            delivery_kind="final",
                            status="blocked",
                        ),
                    )
                    await self._publish_phase1_event(
                        session_key=session_key,
                        kind="primary_path_blocked",
                        payload={"path": "native_loop", "error": str(e), "reason": "artifact_execute_no_legacy_fallback"},
                    )
                    return blocked_result
                await self._publish_phase1_event(
                    session_key=session_key,
                    kind="primary_path_fallback",
                    payload={"from": "native_loop", "to": "runtime_v2", "error": str(e)},
                )

        await self._publish_phase1_event(
            session_key=session_key,
            kind="primary_path_selected",
            payload={"path": "runtime_v2", "runtime_action": getattr(ingress, "_runtime_action", None)},
        )
        return await self._run_runtime_v2_turn(
            update=update,
            session_key=session_key,
            text=text,
            state=state,
            ack_text=ack_text,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
            chat_id=chat_id,
        )

    async def _run_native_loop_turn(
        self,
        update: Optional[Update],
        session_key: str,
        text: str,
        state,
        ack_text: Optional[str],
        resume_checkpoint: Optional[dict] = None,
        chat_id: Optional[int] = None,
        trace_id: Optional[str] = None,
        ingress_message_id: Optional[int] = None,
    ) -> TelegramTurnResult:
        native_loop = self._get_native_loop()
        native_hooks = self._get_native_openemotion_hooks()
        turn_id = state.active_turn_id or state.start_turn()
        runtime_action = (state.ingress_context or {}).get("runtime_action")
        if runtime_action == "execute_task" and state.task_status in {"idle", "waiting_input", "resumable_pause"}:
            state.mark_task_started(goal=text)
        if native_hooks and native_hooks.enabled:
            try:
                native_hooks.process_ingress(
                    session_id=session_key,
                    turn_id=turn_id,
                    source="telegram",
                    user_input=text,
                    state=state,
                    evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
                )
            except Exception as e:
                logger.exception("native_openemotion.ingress.failed session=%s err=%s", session_key, e)

        if ack_text and update is not None:
            state.mark_task_started(goal=text)
            try:
                await self._send_reply(update, ack_text, finalize_evidence=False)
            except Exception:
                pass

        async def emit_native_progress(phase_key: str, payload: Optional[dict] = None) -> None:
            if runtime_action != "execute_task":
                return
            if self._should_use_run_item_timeline(state):
                return
            progress_text = self._build_autonomy_progress_text(phase_key, payload)
            await self._send_autonomy_progress_update(
                state=state,
                phase_key=phase_key,
                text=progress_text,
                update=update,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )

        if self._should_use_run_item_timeline(state):
            await self._ensure_active_run_item_message(
                state=state,
                session_key=session_key,
                update=update,
                chat_id=chat_id,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )

        result = await native_loop.run_turn(
            session_key=session_key,
            user_input=text,
            ingress_context=self._hydrate_artifact_ingress_context(state),
            proto_self_context=state.proto_self_context,
            resume_checkpoint=resume_checkpoint,
            progress_callback=emit_native_progress,
        )
        await self._publish_phase1_event(
            session_key=session_key,
            kind="contract_runtime_started",
            payload={
                "trace_schema": "contract_runtime_v1",
                "runtime_action": (state.ingress_context or {}).get("runtime_action"),
                "artifact_id": ((state.ingress_context or {}).get("resolved_target") or {}).get("artifact_id"),
            },
        )
        task_contract = getattr(result, "task_contract", None)
        next_step_decision = getattr(result, "next_step_decision", None)
        verification_result = getattr(result, "verification_result", None)
        if ((state.ingress_context or {}).get("resolved_target") or {}).get("artifact_id"):
            await self._publish_phase1_event(
                session_key=session_key,
                kind="artifact_envelope_ready",
                payload={
                    "trace_schema": "contract_runtime_v1",
                    "artifact_id": ((state.ingress_context or {}).get("resolved_target") or {}).get("artifact_id"),
                    "filename": ((state.ingress_context or {}).get("resolved_target") or {}).get("filename"),
                },
            )
        if task_contract:
            state.set_task_contract(task_contract)
            await self._publish_phase1_event(
                session_key=session_key,
                kind="contract_locked",
                payload=self._build_contract_event_payload(
                    state=state,
                    event_kind="contract_locked",
                    contract=task_contract,
                ),
            )
        if next_step_decision:
            state.set_next_step_decision(next_step_decision)
            await self._publish_phase1_event(
                session_key=session_key,
                kind="next_step_decided",
                payload=self._build_contract_event_payload(
                    state=state,
                    event_kind="next_step_decided",
                    next_step=next_step_decision,
                ),
            )

        if result.tool_results:
            for step_index, tool_entry in enumerate(result.tool_results):
                tool_result = tool_entry.get("result") or {}
                if tool_entry.get("tool_name") == "read_artifact":
                    if tool_result.get("success") and tool_result.get("output"):
                        state.ingress_context = state.ingress_context or {}
                        state.ingress_context["resolved_artifact_text"] = tool_result.get("output")
                        state.last_inferred_action = "execute"
                    await self._publish_phase1_event(
                        session_key=session_key,
                        kind="artifact_read_started",
                        payload={
                            "trace_schema": "contract_runtime_v1",
                            "artifact_id": ((state.ingress_context or {}).get("resolved_target") or {}).get("artifact_id"),
                        },
                    )
                state.set_last_tool_result_payload({
                    "success": tool_result.get("success"),
                    "tool": tool_entry.get("tool_name"),
                    "stdout": str(tool_result.get("output") or ""),
                    "stderr": str(tool_result.get("error") or ""),
                    "exit_code": 0 if tool_result.get("success") else 1,
                    "metadata": tool_result.get("metadata") or {},
                    "raw": tool_result,
                })
                state.current_step = f"tool:{tool_entry.get('tool_name')}"
                state.task_status = "running"
                if native_hooks and native_hooks.enabled:
                    try:
                        native_hooks.process_external_result(
                            session_id=session_key,
                            turn_id=turn_id,
                            step=step_index,
                            state=state,
                            evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
                        )
                    except Exception as e:
                        logger.exception("native_openemotion.external_result.failed session=%s err=%s", session_key, e)
                await self._publish_phase1_event(
                    session_key=session_key,
                    kind="native_tool_result",
                    payload={
                        "tool_name": tool_entry.get("tool_name"),
                        "success": tool_result.get("success"),
                        "output_preview": str(tool_result.get("output") or "")[:300],
                        "error_preview": str(tool_result.get("error") or "")[:200],
                    },
                )
                await self._publish_tool_delivery_bridge_event(
                    session_key=session_key,
                    tool_result=state.last_tool_result,
                    reply_text=getattr(result, "reply_text", "") or "",
                    delivery_kind="final" if getattr(result, "reply_text", "") else None,
                    source="native_contract_execute",
                    trace_id=trace_id,
                    ingress_message_id=ingress_message_id,
                )
                if tool_entry.get("tool_name") == "read_artifact":
                    artifact_event_kind = "artifact_read_completed" if tool_result.get("success") else "artifact_read_timeout"
                    await self._publish_phase1_event(
                        session_key=session_key,
                        kind=artifact_event_kind,
                        payload={
                            "trace_schema": "contract_runtime_v1",
                            "artifact_id": ((state.ingress_context or {}).get("resolved_target") or {}).get("artifact_id"),
                            "stage_error_code": (tool_result.get("metadata") or {}).get("stage_error_code"),
                            "success": bool(tool_result.get("success")),
                            "error": tool_result.get("error"),
                        },
                    )
        if verification_result:
            state.record_verification(verification_result)
            await self._publish_phase1_event(
                session_key=session_key,
                kind="step_verified",
                payload=self._build_contract_event_payload(
                    state=state,
                    event_kind="step_verified",
                    verification=verification_result,
                ),
            )
            if verification_result.get("need_relock"):
                await self._publish_phase1_event(
                    session_key=session_key,
                    kind="need_relock",
                    payload=self._build_contract_event_payload(
                        state=state,
                        event_kind="need_relock",
                        verification=verification_result,
                    ),
                )

        if result.reply_text:
            verification = verification_result or {}
            if verification.get("need_relock"):
                state.task_status = "blocked"
                state.waiting_for_user_input = True
                state.contract_phase = "re_lock_needed"
            elif next_step_decision and next_step_decision.get("action_type") == "ask_user":
                state.task_status = "waiting_input"
                state.waiting_for_user_input = True
            else:
                state.mark_task_completed()
            turn_result = TelegramTurnResult(
                status="waiting_input" if state.waiting_for_user_input else "completed_verified",
                state=state,
                reply=TelegramTurnReply(
                    reply_text=result.reply_text,
                    delivery_kind="final",
                    status="waiting_input" if state.waiting_for_user_input else "completed_verified",
                ),
                finish_reason=getattr(result, "finish_reason", None),
                checkpoint_payload=getattr(result, "checkpoint_payload", None),
            )
            self._finalize_native_openemotion_turn(
                session_key=session_key,
                turn_id=turn_id,
                state=state,
                turn_result=turn_result,
                native_hooks=native_hooks,
            )
            if native_hooks and native_hooks.enabled:
                try:
                    native_hooks.capture_response_plan(
                        result=turn_result,
                        evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
                    )
                except Exception as e:
                    logger.exception("native_openemotion.response_plan.failed session=%s err=%s", session_key, e)
            return turn_result

        if getattr(result, "status", None) == "resumable_pause":
            state.task_status = "resumable_pause"
            state.waiting_for_user_input = False
            state.contract_phase = "planning_stalled"
            return TelegramTurnResult(
                status="resumable_pause",
                state=state,
                reply=TelegramTurnReply(
                    reply_text="",
                    delivery_kind="progress",
                    status="resumable_pause",
                    suppressible=True,
                ),
                finish_reason=getattr(result, "finish_reason", None),
                checkpoint_payload=getattr(result, "checkpoint_payload", None),
            )

        failed_tool = bool(state.last_tool_result) and not bool(state.last_tool_result.get("success"))
        if failed_tool:
            state.task_status = "blocked"
            state.waiting_for_user_input = True
            turn_result = TelegramTurnResult(
                status="blocked",
                state=state,
                reply=TelegramTurnReply(
                    reply_text=self._build_native_failure_reply(state),
                    delivery_kind="final",
                    status="blocked",
                ),
                finish_reason=getattr(result, "finish_reason", None),
                checkpoint_payload=getattr(result, "checkpoint_payload", None),
            )
            self._finalize_native_openemotion_turn(
                session_key=session_key,
                turn_id=turn_id,
                state=state,
                turn_result=turn_result,
                native_hooks=native_hooks,
            )
            if native_hooks and native_hooks.enabled:
                try:
                    native_hooks.capture_response_plan(
                        result=turn_result,
                        evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
                    )
                except Exception as e:
                    logger.exception("native_openemotion.response_plan.failed session=%s err=%s", session_key, e)
            return turn_result

        state.task_status = "waiting_input"
        state.waiting_for_user_input = True
        turn_result = TelegramTurnResult(
            status="waiting_input",
            state=state,
            reply=TelegramTurnReply(
                reply_text="",
                delivery_kind="progress",
                status="waiting_input",
                suppressible=True,
            ),
            finish_reason=getattr(result, "finish_reason", None),
            checkpoint_payload=getattr(result, "checkpoint_payload", None),
        )
        self._finalize_native_openemotion_turn(
            session_key=session_key,
            turn_id=turn_id,
            state=state,
            turn_result=turn_result,
            native_hooks=native_hooks,
        )
        if native_hooks and native_hooks.enabled:
            try:
                native_hooks.capture_response_plan(
                    result=turn_result,
                    evidence_collector=get_evidence_collector() if _EVIDENCE_COLLECTOR_AVAILABLE else None,
                )
            except Exception as e:
                logger.exception("native_openemotion.response_plan.failed session=%s err=%s", session_key, e)
        return turn_result

    async def _deliver_runtime_v2_result(
        self,
        update: Update,
        state,
        result: TelegramTurnResult,
        is_challenge_turn: bool,
        ingress_message_id: Optional[int] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        session_key = state.session_id
        latest_ingress_id = self._latest_message_id_by_session.get(session_key)

        # 日志点3: delivery 前打印 latest ingress id
        logger.info(
            "runtime_v2.delivery.pre trace=%s session=%s ingress_msg_id=%s latest_ingress_id=%s is_stale=%s",
            trace_id, session_key, ingress_message_id, latest_ingress_id,
            self._is_stale_reply(session_key, ingress_message_id)
        )

        runtime_action = (state.ingress_context or {}).get("runtime_action")
        if runtime_action == "execute_task" and isinstance(state.autonomy_context, dict):
            await self._deliver_runtime_progress_events(
                state=state,
                update=update,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )

        output_verdict, response_plan = await self._finalize_runtime_delivery_contract(
            session_key=session_key,
            state=state,
            result=result,
            source="runtime_v2",
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
        )

        delivery = self.telegram_runtime_bridge.plan_delivery(result, state, is_challenge_turn)
        if not delivery.should_send:
            logger.info("runtime_v2.turn.delivery session=%s should_send=false", state.session_id)
            return

        # Stale reply suppression
        if self._is_stale_reply(session_key, ingress_message_id):
            logger.warning(
                "runtime_v2.delivery.stale_suppressed trace=%s session=%s ingress_msg_id=%s latest_ingress_id=%s",
                trace_id, session_key, ingress_message_id, latest_ingress_id
            )
            return

        hold_allowed, hold_reason = self._chat_hold_for_followup_allowed(
            session_key=session_key,
            state=state,
            update=update,
            result=result,
            response_plan=response_plan,
            output_verdict=output_verdict,
        )
        if hold_allowed:
            hold_result = await self._enqueue_chat_hold_followup(
                session_key=session_key,
                state=state,
                response_plan=response_plan,
                output_verdict=output_verdict,
                trace_id=trace_id,
                ingress_message_id=ingress_message_id,
            )
            if hold_result.get("status") == "queued":
                state.mark_turn_terminal()
                logger.info(
                    "runtime_v2.delivery.held_for_followup trace=%s session=%s cadence=%s reason=%s",
                    trace_id,
                    session_key,
                    getattr(response_plan, "chat_cadence_mode", None),
                    hold_reason,
                )
                return
            logger.info(
                "runtime_v2.delivery.hold_fallback trace=%s session=%s cadence=%s hold_result=%s",
                trace_id,
                session_key,
                getattr(response_plan, "chat_cadence_mode", None),
                hold_result.get("reason"),
            )

        # 日志点2: final delivery 记录 source ingress
        logger.info(
            "runtime_v2.delivery.final trace=%s session=%s source_ingress_msg_id=%s delivery_kind=%s reply_len=%d",
            trace_id, session_key, ingress_message_id,
            result.delivery_kind if hasattr(result, 'delivery_kind') else 'final',
            len(delivery.text)
        )

        # 直接发送，不再用 should_send_failure_notice 判断普通消息
        if delivery.text:
            await self._publish_phase1_event(
                session_key=session_key,
                kind="telegram_delivery",
                trace_id=trace_id,
                message_id=ingress_message_id,
                payload={
                    "text": delivery.text[:1000],
                    "delivery_kind": getattr(result, "delivery_kind", "final"),
                    "status": result.status,
                    "reply_authority": getattr(output_verdict, "applied_authority", None),
                    "reply_origin": getattr(output_verdict, "reply_origin", None),
                },
            )
            send_result = await self._send_reply(update, delivery.text)
            if (
                getattr(output_verdict, "evidence_snapshot", None)
                and getattr(output_verdict, "fidelity_mode", None) == "verbatim"
                and getattr(output_verdict, "fidelity_gap", None) is False
            ):
                state.update_last_delivered_evidence_context(
                    delivery_was_chunked=bool((send_result or {}).get("was_chunked")),
                    source_assistant_message_id=(send_result or {}).get("last_message_id"),
                )
            recent_result_context = dict(getattr(response_plan, "metadata", None) or {}).get("recent_result_context")
            if isinstance(recent_result_context, dict) and recent_result_context:
                state.update_recent_delivered_result_context(
                    delivery_was_chunked=bool((send_result or {}).get("was_chunked")),
                    source_assistant_message_id=(send_result or {}).get("last_message_id"),
                )
            self._finalize_pending_result_continuation_after_response(state, response_plan, result.status)
            if getattr(result, "delivery_kind", "final") in {"final", "chat"} or result.status in {
                "chat",
                "completed_verified",
                "completed",
                "blocked",
                "failed",
            }:
                state.final_sent = True
                state.mark_turn_terminal()

            if (
                result.status in {"completed_verified", "completed", "blocked", "failed"}
                and runtime_action != "execute_task"
                and not state.get_run_items()
            ):
                preserve_evidence_context = bool(
                    getattr(output_verdict, "evidence_snapshot", None)
                    and getattr(output_verdict, "fidelity_mode", None) == "verbatim"
                    and getattr(output_verdict, "fidelity_gap", None) is False
                )
                preserve_recent_result_context = bool(
                    isinstance(dict(getattr(response_plan, "metadata", None) or {}).get("recent_result_context"), dict)
                    and dict(getattr(response_plan, "metadata", None) or {}).get("recent_result_context")
                )
                state.clear_terminal_execution_residue(
                    preserve_evidence_context=preserve_evidence_context,
                    preserve_recent_result_context=preserve_recent_result_context,
                )

    async def _handle_with_new_runtime(
        self,
        update: Update,
        text: str,
        chat_id: int,
        user_id: int,
        username: Optional[str],
        trace_id: Optional[str] = None,
    ) -> None:
        """使用新 runtime 处理消息"""
        set_telegram_bot(self.app.bot)
        context_store = get_session_context_store()

        session_key = self._resolve_session_key(update, chat_id, user_id)
        state = self._get_runtime_state(session_key)
        ingress_message_id = update.message.message_id if update.message else None

        if not await self._ensure_subject_ingress(
            update=update,
            session_key=session_key,
            state=state,
            text=text,
            trace_id=trace_id,
            ingress_message_id=ingress_message_id,
            turn_prefix="new_runtime",
        ):
            return

        # 写入用户消息到会话上下文，供下一轮 OpenEmotion 读取
        context_store.add_turn(session_key, "user", text)

        logger.info(f"[trace={trace_id}] session={session_key} entered new-runtime path")

        # 不再发送 generic ACK（兼容路径也统一行为）
        # typing 指示器已足够表示系统在处理

        result = None
        try:
            # 任务类消息偶发卡住时，不能静默：加超时并兜底回复
            logger.info(f"[trace={trace_id}] run_agent start")
            result = await asyncio.wait_for(
                run_agent(
                    prompt=text,
                    session_key=session_key,
                    user_id=str(user_id),
                    channel="telegram",
                    sender_name=username,
                    message_to=str(chat_id),
                    extra_context={
                        "telegram_message_id": str(update.message.message_id) if update.message else None,
                        "telegram_reply_to_message_id": str(update.message.reply_to_message.message_id) if update.message and update.message.reply_to_message else None,
                    },
                ),
                timeout=90,
            )
        except asyncio.TimeoutError:
            logger.error(f"[trace={trace_id}] run_agent timeout: session={session_key} text={text[:120]}")
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text="我收到了这条请求，但处理超时了。我马上重试，你也可以再发一次。",
                status="new_runtime_timeout",
                delivery_kind="final",
                authority_source="host_runtime_fallback",
                reply_authority="host_runtime_timeout",
                metadata={"conversation_act": "runtime_timeout"},
            )
            return
        except Exception as e:
            logger.exception(f"[trace={trace_id}] run_agent crashed: session={session_key} text={text[:120]} err={e}")
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text="我这一步中断了，但请求已经收到。请再发一次，我继续处理。",
                status="new_runtime_error",
                delivery_kind="final",
                authority_source="host_runtime_fallback",
                reply_authority="host_runtime_error",
                metadata={"conversation_act": "runtime_error"},
            )
            return

        logger.info(
            f"[trace={trace_id}] New runtime: session={session_key} status={result.status.value} "
            f"duration={result.duration_ms}ms"
        )

        if result.reply_text:
            ingress_message_id = update.message.message_id if update.message else None
            if self._is_stale_reply(session_key, ingress_message_id):
                logger.warning(
                    f"[trace={trace_id}] stale reply suppressed: session={session_key} ingress_message_id={ingress_message_id} "
                    f"latest={self._latest_message_id_by_session.get(session_key)}"
                )
                return
            delivery_identity = self._build_delivery_identity(
                session_key=session_key,
                ingress_message_id=ingress_message_id,
                reply_text=result.reply_text,
                request_id=getattr(result, "request_id", None),
                delivery_kind="final",
            )
            if self._delivery_dedupe_policy.should_suppress(delivery_identity):
                logger.warning(
                    f"[trace={trace_id}] duplicate outbound suppressed: session={session_key} ingress_message_id={ingress_message_id} request_id={getattr(result, 'request_id', None)}"
                )
                return
            # 写入 assistant 回复到会话上下文，供后续轮次读取
            context_store.add_turn(session_key, "assistant", result.reply_text)
            self._delivery_dedupe_policy.mark_sent(delivery_identity)
            logger.info(f"[trace={trace_id}] sending final reply")
            await self._send_host_owned_reply(
                update,
                state=state,
                reply_text=result.reply_text,
                status=str(getattr(result, "status", None).value if hasattr(getattr(result, "status", None), "value") else getattr(result, "status", "completed")),
                delivery_kind="final",
                authority_source="host_runtime_result",
                reply_authority="host_runtime",
                metadata={"conversation_act": "runtime_result"},
            )
        else:
            logger.warning(f"[trace={trace_id}] result.reply_text is empty")

    async def _handle_with_legacy_router(
        self,
        update: Update,
        text: str,
        chat_id: int,
        user_id: int,
        username: Optional[str],
    ) -> None:
        """使用旧路由处理消息 (兼容模式)"""
        ctx = CommandContext(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            args="",
            message_text=text
        )

        result = handle_natural_language(ctx)
        await self._send_result(update, result)

    async def _with_typing(self, update: Update, coro_factory):
        async with self._typing_indicator(update):
            return await coro_factory()

    @asynccontextmanager
    async def _typing_indicator(self, update: Update):
        if not self.app or not getattr(self.app, "bot", None) or not update.effective_chat:
            yield
            return

        chat_id = update.effective_chat.id
        stop_typing = asyncio.Event()

        try:
            await self.app.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass

        async def typing_loop():
            while not stop_typing.is_set():
                try:
                    await asyncio.wait_for(stop_typing.wait(), timeout=4.0)
                    break
                except asyncio.TimeoutError:
                    try:
                        await self.app.bot.send_chat_action(chat_id=chat_id, action="typing")
                    except Exception:
                        pass

        typing_task = asyncio.create_task(typing_loop())
        try:
            yield
        finally:
            stop_typing.set()
            try:
                await typing_task
            except Exception:
                pass

    async def _send_reply(self, update: Update, text: str, use_markdown: bool = False, finalize_evidence: bool = True):
        """发送回复

        Args:
            update: Telegram update
            text: 消息文本
            use_markdown: 是否使用 Markdown 格式（仅用于代码生成的可控消息）
        """
        chunks = self._chunk_telegram_text(text)
        sent_count = 0
        last_message_id = None

        for index, chunk in enumerate(chunks):
            sent_message = None
            try:
                if use_markdown:
                    from telegram.helpers import escape_markdown

                    escaped_text = escape_markdown(chunk, version=1)
                    sent_message = await update.message.reply_text(escaped_text, parse_mode="Markdown")
                else:
                    sent_message = await update.message.reply_text(chunk)
            except Exception as e:
                logger.warning(f"Send failed (markdown={use_markdown}): {e}")
                try:
                    sent_message = await update.message.reply_text(chunk)
                except Exception as e2:
                    logger.error(f"Failed to send plain text chunk: {e2}")
                    continue

            sent_count += 1
            last_message_id = getattr(sent_message, "message_id", None)
            self._capture_telegram_outbox_record(
                sent_message,
                text_length=len(chunk),
                text_preview=chunk,
                finalize_evidence=finalize_evidence and index == len(chunks) - 1,
            )

        return {
            "sent_count": sent_count,
            "was_chunked": len(chunks) > 1,
            "last_message_id": last_message_id,
        }

    async def _send_result(self, update: Update, result: CommandResult) -> None:
        """Send CommandResult as Telegram message.

        CommandResult 通常是代码生成的格式化输出，支持 Markdown。
        """
        chat_id = update.effective_chat.id if update.effective_chat else 0
        user_id = update.effective_user.id if update.effective_user else 0
        session_key = self._resolve_session_key(update, chat_id, user_id)
        await self._send_host_owned_reply(
            update,
            state=self._get_runtime_state(session_key),
            reply_text=result.message,
            status="command_result",
            delivery_kind="final",
            authority_source="host_command_result",
            reply_authority="host_command",
            metadata={"conversation_act": "command_result", "command_success": result.success},
            use_markdown=True,
        )

    def setup(self) -> None:
        """Set up bot handlers."""
        if self._setup_complete and self.app is not None:
            logger.warning("TelegramBot.setup() called after setup already completed; reusing existing Application")
            return

        self.app = Application.builder().token(self.token).build()

        # Register command handlers
        commands = [
            "start", "help", "new", "reset", "run", "status", "tasks", "resume",
            "pause", "retry", "abort", "report", "memory", "context", "prompt", "proto",
            "replace", "append", "cancel",
        ]
        self._known_commands = set(commands)

        for cmd in commands:
            self.app.add_handler(CommandHandler(cmd, self.handle_command))

        # Handle all other messages
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Handle document attachments
        document_filter = getattr(getattr(filters, "Document", None), "ALL", None)
        if document_filter is not None:
            self.app.add_handler(MessageHandler(document_filter, self.handle_document))

        self._setup_complete = True
        logger.info("Telegram bot handlers registered")

    def run(self) -> None:
        """Run the bot (blocking) with explicit PTB lifecycle control."""
        if self._run_started:
            logger.error("TelegramBot.run() called twice on the same instance; refusing second polling start")
            raise RuntimeError("Telegram bot polling already started on this instance")

        if not self.app:
            self.setup()

        token_tail = (self.token[-6:] if self.token else "unknown")
        fingerprint = f"host={socket.gethostname()} pid={os.getpid()} token_tail={token_tail}"

        logger.info("Starting Telegram bot polling... %s", fingerprint)
        print("\n🤖 Telegram bot is running!")
        print("   Send a message to your bot to test.")
        print("   Press Ctrl+C to stop.\n")
        print(f"   Instance: {fingerprint}")

        self._run_started = True
        try:
            asyncio.run(self._run_polling_lifecycle(fingerprint))
        except Conflict as e:
            logger.error("Telegram polling conflict detected (%s). Exiting process to avoid split-brain pollers.", e)
            raise SystemExit(3)
        except KeyboardInterrupt:
            logger.info("Telegram polling interrupted by user")
            raise

    async def _run_polling_lifecycle(self, fingerprint: str) -> None:
        """Explicit PTB lifecycle for better observability and shutdown control."""
        if self.app is None:
            self.setup()
        assert self.app is not None
        logger.info("telegram.lifecycle setup_done %s", fingerprint)
        try:
            logger.info("telegram.lifecycle initialize_start %s", fingerprint)
            await self.app.initialize()
            logger.info("telegram.lifecycle initialize_done %s", fingerprint)

            logger.info("telegram.lifecycle app_start %s", fingerprint)
            await self.app.start()
            logger.info("telegram.lifecycle app_started %s", fingerprint)
            if self.autonomy_orchestrator is not None:
                self.autonomy_orchestrator.recover_surface("telegram")
            if self._mvp12_proactive_telegram_autodrain_enabled and self.use_runtime_v2:
                self._proactive_telegram_autodrain_task = asyncio.create_task(
                    self._run_proactive_telegram_autodrain_loop()
                )
                logger.info("telegram.lifecycle proactive_autodrain_started %s", fingerprint)

            try:
                command_specs = [
                    BotCommand("start", "开始使用 bot"),
                    BotCommand("help", "查看帮助"),
                    BotCommand("status", "查看当前会话状态"),
                    BotCommand("tasks", "查看任务列表"),
                    BotCommand("memory", "查看记忆摘要"),
                    BotCommand("context", "查看当前加载上下文"),
                    BotCommand("prompt", "查看或重载当前 prompt 文件"),
                    BotCommand("proto", "控制 Proto-Self ingress 版本"),
                    BotCommand("new", "开始新会话"),
                    BotCommand("reset", "重置当前会话"),
                    BotCommand("resume", "恢复任务"),
                    BotCommand("pause", "暂停任务"),
                    BotCommand("retry", "重试上一步"),
                    BotCommand("abort", "终止当前任务"),
                    BotCommand("report", "生成报告"),
                    BotCommand("run", "执行下一步"),
                ]
                await self.app.bot.set_my_commands(command_specs)
                logger.info("telegram.lifecycle commands_registered %s", fingerprint)
            except Exception:
                logger.exception("telegram.lifecycle commands_register_failed %s", fingerprint)

            logger.info("telegram.lifecycle polling_start %s", fingerprint)
            await self.app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            logger.info("telegram.lifecycle polling_started %s", fingerprint)

            while True:
                await asyncio.sleep(1)
        except Conflict:
            logger.exception("telegram.lifecycle polling_conflict %s", fingerprint)
            raise
        finally:
            logger.info("telegram.lifecycle shutdown_start %s", fingerprint)
            if self._proactive_telegram_autodrain_task is not None:
                self._proactive_telegram_autodrain_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._proactive_telegram_autodrain_task
                self._proactive_telegram_autodrain_task = None
            try:
                if self.app.updater and self.app.updater.running:
                    await self.app.updater.stop()
                    logger.info("telegram.lifecycle updater_stopped %s", fingerprint)
            except Exception:
                logger.exception("telegram.lifecycle updater_stop_failed %s", fingerprint)
            try:
                if self.app.running:
                    await self.app.stop()
                    logger.info("telegram.lifecycle app_stopped %s", fingerprint)
            except Exception:
                logger.exception("telegram.lifecycle app_stop_failed %s", fingerprint)
            try:
                await self.app.shutdown()
                logger.info("telegram.lifecycle shutdown_done %s", fingerprint)
            except Exception:
                logger.exception("telegram.lifecycle shutdown_failed %s", fingerprint)

    async def run_async(self) -> None:
        """Run the bot asynchronously."""
        if not self.app:
            self.setup()

        token_tail = (self.token[-6:] if self.token else "unknown")
        fingerprint = f"host={socket.gethostname()} pid={os.getpid()} token_tail={token_tail}"
        logger.info("Starting Telegram bot async polling... %s", fingerprint)
        await self._run_polling_lifecycle(fingerprint)

    async def stop_async(self) -> None:
        """Stop the async bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


def create_bot_from_config(
    *,
    pending_restore_observation: Optional[PendingRestoreObservation] = None,
) -> TelegramBot:
    """
    Create TelegramBot from configuration.

    Returns:
        Configured TelegramBot instance

    Raises:
        ConfigError: If required configuration is missing
    """
    config = get_config()

    # Get token from environment
    token = config.get_env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ConfigError(
            "TELEGRAM_BOT_TOKEN not set. "
            "Set it in your .env file or environment variables."
        )

    # Get allowed chat IDs from config
    telegram_config = config.telegram
    allowed_ids = telegram_config.get("allowed_chat_ids", [])

    return TelegramBot(
        token=token,
        allowed_chat_ids=allowed_ids,
        use_runtime_v2=True,
        pending_restore_observation=pending_restore_observation,
    )


# Global bot instance
_bot: Optional[TelegramBot] = None


def get_bot() -> TelegramBot:
    """Get the global bot instance."""
    global _bot
    if _bot is None:
        _bot = create_bot_from_config()
    return _bot
