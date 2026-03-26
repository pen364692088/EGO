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
import logging
import os
import socket
import uuid
from typing import Optional
import json
import time
from contextlib import asynccontextmanager

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
from app.interaction.session_context_store import get_session_context_store

# E4 Evidence Collector - for capturing outbox_record
try:
    from app.telegram_evidence_collector import get_evidence_collector
    _EVIDENCE_COLLECTOR_AVAILABLE = True
except ImportError:
    _EVIDENCE_COLLECTOR_AVAILABLE = False
from app.runtime_v2 import (
    RuntimeV2Loop,
    RuntimeV2PromptFiles,
    RuntimeV2TelegramBridge,
    RuntimeV2Reply,
    RuntimeV2TurnResult,
)
from app.core_bus import BusEvent, get_message_bus, get_session_worker_pool
from app.session_store import SessionLogManager
from app.agent_core import NativeToolCallingLoop
from app.openemotion_hooks import NativeOpenEmotionHooks

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

    def __init__(self, token: str, allowed_chat_ids: Optional[list[int]] = None, use_new_runtime: bool = True, use_runtime_v2: bool = False):
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
        self.runtime_v2_loop = RuntimeV2Loop() if use_runtime_v2 else None
        self.runtime_v2_bridge = RuntimeV2TelegramBridge() if use_runtime_v2 else None
        self.native_loop = NativeToolCallingLoop() if use_runtime_v2 else None
        self.native_openemotion_hooks = NativeOpenEmotionHooks() if use_runtime_v2 else None
        self._setup_complete = False
        self._run_started = False
        # Stale reply suppression: remember latest ingress message per session.
        self._latest_message_id_by_session: dict[str, int] = {}
        self._delivery_dedupe_policy = DeliveryDedupePolicy()
        self._message_bus = get_message_bus()
        self._session_worker_pool = get_session_worker_pool()
        self._session_log_manager = SessionLogManager()
        self._phase1_bus_ready = False
        # Ingestion Manager
        self._ingestion_manager: Optional[IngestionManager] = None

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

    def is_allowed(self, chat_id: int) -> bool:
        """Check if chat ID is allowed to interact with bot."""
        if self.allowed_chat_ids is None:
            return True
        return chat_id in self.allowed_chat_ids

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

        logger.info(f"Command received: /{command} from user {username or user_id}")

        if command == "context":
            result = self._handle_context_command(update, args, chat_id, user_id, username)
            await self._send_result(update, result)
            return
        if command == "prompt":
            result = self._handle_prompt_command(args)
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

    def _handle_session_reset_command(self, update: Update, command: str, chat_id: int, user_id: int) -> CommandResult:
        session_key = self._resolve_session_key(update, chat_id, user_id)
        context_store = get_session_context_store()
        context_store.clear_session(session_key)
        if self.runtime_v2_loop is not None:
            self.runtime_v2_loop.reset_session(session_key)
        self._latest_message_id_by_session.pop(session_key, None)
        verb = "started fresh" if command == "new" else "reset"
        return CommandResult(
            success=True,
            message=(
                "🆕 *Session Reset*\n\n"
                f"- session_key: `{session_key}`\n"
                f"- action: `{verb}`\n"
                "- context: cleared\n"
                "- runtime_v2_state: reset"
            ),
            data={"session_key": session_key, "action": command, "reset": True},
        )

    def _handle_runtime_status_command(self, update: Update, chat_id: int, user_id: int) -> CommandResult:
        session_key = self._resolve_session_key(update, chat_id, user_id)
        context_store = get_session_context_store()
        recent_turns = context_store.get_recent_turns(session_key, limit=20)
        state = self.runtime_v2_loop.get_state(session_key) if self.runtime_v2_loop is not None else None
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

        # Estimate cost (qianfan pricing: ~$0.001/1K tokens for input, ~$0.002/1K tokens for output)
        cost = (prompt_tokens * 0.000001 + completion_tokens * 0.000002)

        lines = [
            "🦞 *EgoCore Runtime*",
            "🧠 Model: `qianfan/glm-5` · 🔑 `api-key` (llm.yaml)",
            f"🧮 Tokens: `{prompt_k}` in / `{completion_k}` out · 💵 Cost: `${cost:.4f}`",
            f"📚 Context: `{context_k}k/200k ({context_pct}%)` · 🧹 Compactions: `{compactions}`",
            f"Session ID: `{session_key}`",
            f"📜 History: `available` · file: `{history_file}`",
            f"🧵 Session: `{session_key}` • updated {updated_text}",
            "⚙️ Runtime: `runtime_v2` · Think: `off`",
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

        if self.use_runtime_v2 and self.runtime_v2_loop is not None:
            state = self.runtime_v2_loop.get_state(session_key)
            prompt_bundle = RuntimeV2PromptFiles().load()
            lines.extend([
                "",
                "*Runtime v2 State*",
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
            await update.message.reply_text(
                f"收到文件「{document.file_name or 'unnamed'}」，"
                f"但暂不支持此类型（{document.mime_type or 'unknown'}）。"
                f"\n\n支持的类型：txt, md, log, json, yaml, csv"
            )
            return

        async with self._typing_indicator(update):
            # 下载文件
            try:
                file = await context.bot.get_file(document.file_id)
                content = await file.download_as_bytearray()
                content = bytes(content)
            except Exception as e:
                logger.error(f"[trace={trace_id}] failed to download file: {e}")
                await update.message.reply_text(f"文件下载失败：{e}")
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
                await update.message.reply_text(f"文件处理失败：{result.error}")
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
                state = self.runtime_v2_loop.get_state(session_key)
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
                await update.message.reply_text(reply)

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
            state = self.runtime_v2_loop.get_state(session_key)
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
        state = self.runtime_v2_loop.get_state(session_key)

        # 记录 ingress 信息
        ingress_message_id = update.message.message_id if update.message else None
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

        # 如果有额外上下文（如文件内容），合并到用户输入
        if extra_context:
            text = f"{text}\n\n{extra_context}"

        ingress = await self.runtime_v2_bridge.inspect_ingress_semantic(text, state, llm_client=None)
        state.ingress_context = self.runtime_v2_bridge.build_ingress_context(ingress, state)
        pre_runtime = self.runtime_v2_bridge.plan_pre_runtime(ingress, state)
        logger.info("runtime_v2.turn.start session=%s text=%r ingress=%s parser_source=%s", 
                    session_key, text[:200], ingress, 
                    ingress._parsed_intent_graph.parser_source if ingress._parsed_intent_graph else "none")

        if pre_runtime.remember_challenge_turn:
            state.last_challenge_turn = text

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

        result = await self._run_primary_turn(
            update=update,
            session_key=session_key,
            text=text,
            state=state,
            ingress=ingress,
            ack_text=pre_runtime.ack_text,
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

        # 文件-only：强制 waiting_input，不进入 runtime
        if getattr(pre_runtime, 'force_waiting_input', False):
            state.task_status = "waiting_input"
            state.waiting_for_user_input = True
            waiting_text = getattr(pre_runtime, 'waiting_input_text', '收到文件，请告诉我你要做什么。')
            await self._send_reply(update, waiting_text)
            return True

        if getattr(pre_runtime, "direct_reply_text", None):
            await self._send_reply(update, pre_runtime.direct_reply_text)
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
    ) -> RuntimeV2TurnResult:
        async def run_once() -> RuntimeV2TurnResult:
            if ack_text:
                state.mark_task_started(goal=text)
                try:
                    await self._send_reply(update, ack_text)
                except Exception:
                    pass

            # 闭环2：把 pending_artifacts 信息注入 user_input，帮 LLM 知道要执行什么
            enhanced_input = text
            if state.last_uploaded_artifact:
                filename = state.last_uploaded_artifact.get("filename", "未知文件")
                enhanced_input = f"{text}\n\n[目标文件: {filename}]"

            return await self.runtime_v2_loop.run_turn_typed(session_id=session_key, user_input=enhanced_input)

        return await run_once()

    def _should_use_native_loop(self, ingress, state) -> bool:
        if self.native_loop is None:
            return False
        runtime_action = getattr(ingress, "_runtime_action", None)
        if runtime_action != "execute_task":
            return False
        if getattr(ingress, "is_file_only", False):
            return False
        if state.waiting_for_user_input:
            return False
        return True

    async def _run_primary_turn(
        self,
        update: Update,
        session_key: str,
        text: str,
        state,
        ingress,
        ack_text: Optional[str],
    ) -> RuntimeV2TurnResult:
        if self._should_use_native_loop(ingress, state):
            try:
                return await self._run_native_loop_turn(
                    update=update,
                    session_key=session_key,
                    text=text,
                    state=state,
                    ack_text=ack_text,
                )
            except Exception as e:
                logger.exception("native_loop.failed session=%s err=%s; falling back to runtime_v2", session_key, e)

        return await self._run_runtime_v2_turn(
            update=update,
            session_key=session_key,
            text=text,
            state=state,
            ack_text=ack_text,
        )

    async def _run_native_loop_turn(
        self,
        update: Update,
        session_key: str,
        text: str,
        state,
        ack_text: Optional[str],
    ) -> RuntimeV2TurnResult:
        turn_id = state.active_turn_id or state.start_turn()
        if self.native_openemotion_hooks and self.native_openemotion_hooks.enabled:
            try:
                self.native_openemotion_hooks.process_ingress(
                    session_id=session_key,
                    turn_id=turn_id,
                    source="telegram",
                    user_input=text,
                    state=state,
                )
            except Exception as e:
                logger.exception("native_openemotion.ingress.failed session=%s err=%s", session_key, e)

        if ack_text:
            state.mark_task_started(goal=text)
            try:
                await self._send_reply(update, ack_text)
            except Exception:
                pass

        result = await self.native_loop.run_turn(
            session_key=session_key,
            user_input=text,
            ingress_context=state.ingress_context,
            proto_self_context=state.proto_self_context,
        )

        if result.tool_results:
            for step_index, tool_entry in enumerate(result.tool_results):
                tool_result = tool_entry.get("result") or {}
                state.last_tool_result = {
                    "success": tool_result.get("success"),
                    "tool": tool_entry.get("tool_name"),
                    "stdout": str(tool_result.get("output") or ""),
                    "stderr": str(tool_result.get("error") or ""),
                    "exit_code": 0 if tool_result.get("success") else 1,
                    "metadata": tool_result.get("metadata") or {},
                    "raw": tool_result,
                }
                state.current_step = f"tool:{tool_entry.get('tool_name')}"
                state.task_status = "running"
                if self.native_openemotion_hooks and self.native_openemotion_hooks.enabled:
                    try:
                        self.native_openemotion_hooks.process_external_result(
                            session_id=session_key,
                            turn_id=turn_id,
                            step=step_index,
                            state=state,
                        )
                    except Exception as e:
                        logger.exception("native_openemotion.external_result.failed session=%s err=%s", session_key, e)

        if result.reply_text:
            state.mark_task_completed()
            turn_result = RuntimeV2TurnResult(
                status="completed_verified",
                state=state,
                reply=RuntimeV2Reply(
                    reply_text=result.reply_text,
                    delivery_kind="final",
                    status="completed_verified",
                ),
            )
            if self.native_openemotion_hooks and self.native_openemotion_hooks.enabled:
                try:
                    self.native_openemotion_hooks.capture_response_plan(result=turn_result)
                except Exception as e:
                    logger.exception("native_openemotion.response_plan.failed session=%s err=%s", session_key, e)
            return turn_result

        state.task_status = "waiting_input"
        state.waiting_for_user_input = True
        turn_result = RuntimeV2TurnResult(
            status="waiting_input",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="",
                delivery_kind="progress",
                status="waiting_input",
                suppressible=True,
            ),
        )
        if self.native_openemotion_hooks and self.native_openemotion_hooks.enabled:
            try:
                self.native_openemotion_hooks.capture_response_plan(result=turn_result)
            except Exception as e:
                logger.exception("native_openemotion.response_plan.failed session=%s err=%s", session_key, e)
        return turn_result

    async def _deliver_runtime_v2_result(
        self,
        update: Update,
        state,
        result: RuntimeV2TurnResult,
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

        delivery = self.runtime_v2_bridge.plan_delivery(result, state, is_challenge_turn)
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
                },
            )
            await self._send_reply(update, delivery.text)

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
            await self._send_reply(update, "我收到了这条请求，但处理超时了。我马上重试，你也可以再发一次。")
            return
        except Exception as e:
            logger.exception(f"[trace={trace_id}] run_agent crashed: session={session_key} text={text[:120]} err={e}")
            await self._send_reply(update, "我这一步中断了，但请求已经收到。请再发一次，我继续处理。")
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
            await self._send_reply(update, result.reply_text)
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

    async def _send_reply(self, update: Update, text: str, use_markdown: bool = False) -> None:
        """发送回复

        Args:
            update: Telegram update
            text: 消息文本
            use_markdown: 是否使用 Markdown 格式（仅用于代码生成的可控消息）
        """
        sent_message = None
        try:
            if use_markdown:
                # 对 Markdown 特殊字符进行转义
                from telegram.helpers import escape_markdown
                escaped_text = escape_markdown(text, version=1)
                sent_message = await update.message.reply_text(escaped_text, parse_mode="Markdown")
            else:
                sent_message = await update.message.reply_text(text)
        except Exception as e:
            logger.warning(f"Send failed (markdown={use_markdown}): {e}")
            # Fallback to plain text
            try:
                sent_message = await update.message.reply_text(text)
            except Exception as e2:
                logger.error(f"Failed to send plain text: {e2}")
                # 最后尝试截断
                if len(text) > 4000:
                    try:
                        sent_message = await update.message.reply_text(text[:4000] + "\n... (已截断)")
                    except Exception as e3:
                        logger.error(f"Failed to send truncated: {e3}")

        # E4 Evidence: Capture outbox_record
        if sent_message and _EVIDENCE_COLLECTOR_AVAILABLE:
            try:
                collector = get_evidence_collector()
                outbox_record = {
                    "chat_id": sent_message.chat.id if sent_message.chat else None,
                    "message_id": sent_message.message_id,
                    "date": sent_message.date.isoformat() if sent_message.date else None,
                    "text_length": len(text),
                    "success": True,
                }
                collector.capture_outbox_record(outbox_record)
                logger.info(f"[E4-EVIDENCE] outbox_record captured: chat_id={outbox_record['chat_id']} msg_id={outbox_record['message_id']}")

                # Finalize and save the sample
                sample = collector.finalize_sample()
                if sample:
                    logger.info(f"[E4-EVIDENCE] Sample finalized: {sample.sample_id} complete={sample.is_complete()}")
            except Exception as e:
                logger.warning(f"[E4-EVIDENCE] Failed to capture outbox_record: {e}")

    async def _send_result(self, update: Update, result: CommandResult) -> None:
        """Send CommandResult as Telegram message.

        CommandResult 通常是代码生成的格式化输出，支持 Markdown。
        """
        try:
            from telegram.helpers import escape_markdown
            escaped_message = escape_markdown(result.message, version=1)
            await update.message.reply_text(escaped_message, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Markdown send failed: {e}")
            # Fallback to plain text
            try:
                await update.message.reply_text(result.message)
            except Exception as e2:
                logger.error(f"Failed to send plain text: {e2}")
                # 最后尝试截断
                if len(result.message) > 4000:
                    try:
                        truncated = result.message[:4000] + "\n... (已截断)"
                        await update.message.reply_text(truncated)
                    except Exception as e3:
                        logger.error(f"Failed to send truncated: {e3}")

    def setup(self) -> None:
        """Set up bot handlers."""
        if self._setup_complete and self.app is not None:
            logger.warning("TelegramBot.setup() called after setup already completed; reusing existing Application")
            return

        self.app = Application.builder().token(self.token).build()

        # Register command handlers
        commands = [
            "start", "help", "new", "reset", "run", "status", "tasks", "resume",
            "pause", "retry", "abort", "report", "memory", "context", "prompt"
        ]
        self._known_commands = set(commands)

        for cmd in commands:
            self.app.add_handler(CommandHandler(cmd, self.handle_command))

        # Handle all other messages
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Handle document attachments
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))

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

            try:
                command_specs = [
                    BotCommand("start", "开始使用 bot"),
                    BotCommand("help", "查看帮助"),
                    BotCommand("status", "查看当前会话状态"),
                    BotCommand("tasks", "查看任务列表"),
                    BotCommand("memory", "查看记忆摘要"),
                    BotCommand("context", "查看当前加载上下文"),
                    BotCommand("prompt", "查看或重载当前 prompt 文件"),
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


def create_bot_from_config() -> TelegramBot:
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

    return TelegramBot(token=token, allowed_chat_ids=allowed_ids, use_runtime_v2=True)


# Global bot instance
_bot: Optional[TelegramBot] = None


def get_bot() -> TelegramBot:
    """Get the global bot instance."""
    global _bot
    if _bot is None:
        _bot = create_bot_from_config()
    return _bot
