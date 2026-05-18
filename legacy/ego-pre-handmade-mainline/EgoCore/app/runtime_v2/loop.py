from __future__ import annotations

import uuid
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Awaitable, Callable, Dict, Optional
from datetime import datetime
import re

from .action_protocol import RuntimeV2Action
from .chat_reply_engine import ChatReplyEngine
from .decision_engine import RuntimeV2DecisionEngine
from .runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from .run_items import RunEvent
from .state import RuntimeV2State
from .tool_broker import RuntimeV2ToolBroker
from .transition import RuntimeV2TransitionEngine, _build_host_blocked_summary
from .verifier import RuntimeV2Verifier
from .progress_events import ProgressEvent, is_terminal_event
from .proto_self_runtime import RuntimeV2ProtoSelfRuntime, assess_risk_level

# Proto-Self Kernel Adapter - deferred loading
try:
    from app.openemotion_adapter import ProtoSelfAdapter, ProtoSelfTraceBridge
    _PROTO_SELF_IMPORT_OK = True
except ImportError as e:
    import logging
    logging.warning(f"[PSK-IMPORT] ImportError: {e}")
    _PROTO_SELF_IMPORT_OK = False
    ProtoSelfAdapter = None
    ProtoSelfTraceBridge = None
except Exception as e:
    import logging
    logging.warning(f"[PSK-IMPORT] Unexpected error: {e}")
    _PROTO_SELF_IMPORT_OK = False
    ProtoSelfAdapter = None
    ProtoSelfTraceBridge = None

# Config check deferred to runtime - module import may happen before load_config()
_PROTO_SELF_ENABLED = None  # None means not yet checked

# E4 Evidence Collector - for capturing normalized_event and openemotion_result
_EVIDENCE_COLLECTOR_AVAILABLE = False
try:
    from app.telegram_evidence_collector import get_evidence_collector
    _EVIDENCE_COLLECTOR_AVAILABLE = True
except ImportError:
    pass

def _check_proto_self_enabled() -> bool:
    """Runtime check for Proto-Self enabled status."""
    global _PROTO_SELF_ENABLED
    if _PROTO_SELF_ENABLED is None:
        if _PROTO_SELF_IMPORT_OK:
            try:
                from app.config import get_config
                _config = get_config()
                _PROTO_SELF_ENABLED = _config.openemotion.get('enabled', False) if _config else False
            except Exception:
                _PROTO_SELF_ENABLED = False
        else:
            _PROTO_SELF_ENABLED = False
    return _PROTO_SELF_ENABLED

# 用户输入截断阈值
MAX_USER_INPUT_IN_STATE = 300  # 字符（更严格）
WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
SHELL_FILE_READ_PREFIXES = (
    "type ",
    "cat ",
    "more ",
    "get-content",
    "gc ",
)


def _assess_risk_level(user_input: str) -> str:
    return assess_risk_level(user_input)


def _truncate_user_input(text: str) -> str:
    """截断用户输入，防止文件内容等大文本进入 state"""
    if len(text) <= MAX_USER_INPUT_IN_STATE:
        return text
    return text[:MAX_USER_INPUT_IN_STATE] + f"\n... [截断，原文 {len(text)} 字符]"


import logging
logger = logging.getLogger(__name__)

class RuntimeV2Loop:
    def __init__(self) -> None:
        self.tool_broker = RuntimeV2ToolBroker()
        self.verifier = RuntimeV2Verifier()
        self.decision_engine = RuntimeV2DecisionEngine()
        self.chat_reply_engine = ChatReplyEngine()
        self.transition_engine = RuntimeV2TransitionEngine(self.tool_broker, self.verifier)
        self._states: Dict[str, RuntimeV2State] = {}

        # Proto-Self Kernel Adapter (deferred check)
        proto_self_enabled = _check_proto_self_enabled()
        logger.info(f"[PSK-INIT] _PROTO_SELF_IMPORT_OK={_PROTO_SELF_IMPORT_OK}, proto_self_enabled={proto_self_enabled}")
        if _PROTO_SELF_IMPORT_OK and proto_self_enabled:
            self.proto_self_adapter = ProtoSelfAdapter()
            self.proto_self_trace_bridge = ProtoSelfTraceBridge()
            self.proto_self_runtime = RuntimeV2ProtoSelfRuntime(
                adapter=self.proto_self_adapter,
                trace_bridge=self.proto_self_trace_bridge,
                evidence_collector_factory=get_evidence_collector if _EVIDENCE_COLLECTOR_AVAILABLE else None,
            )
            logger.info(f"[PSK-INIT] ProtoSelfAdapter initialized, mirror_dir={self.proto_self_adapter.mirror_dir}")
        else:
            self.proto_self_adapter = None
            self.proto_self_trace_bridge = None
            self.proto_self_runtime = None
            logger.warning(f"[PSK-INIT] Proto-Self NOT available (import_ok={_PROTO_SELF_IMPORT_OK}, enabled={proto_self_enabled})")

    def get_state(self, session_id: str) -> RuntimeV2State:
        if session_id not in self._states:
            self._states[session_id] = RuntimeV2State(session_id=session_id)
        return self._states[session_id]

    def _resolve_explicit_analyze_path(self, state: RuntimeV2State) -> Optional[str]:
        ingress = state.ingress_context or {}
        if ingress.get("request_mode") != "analyze":
            return None

        resolved_target = ingress.get("resolved_target") or state.resolve_target("analyze") or {}
        target_path = resolved_target.get("path")
        if isinstance(target_path, str) and target_path.strip():
            return target_path.strip()

        explicit_target = (state.last_explicit_target or "").strip()
        if not explicit_target:
            return None
        if WINDOWS_PATH_RE.match(explicit_target) or explicit_target.startswith(
            ("/", "/mnt/", "/home/", "/tmp/", "/Users/")
        ):
            return explicit_target
        return None

    def _looks_like_shell_file_display(self, command: str, target_path: str) -> bool:
        lowered = (command or "").strip().lower()
        if not lowered:
            return False

        normalized_target = target_path.lower().replace("\\", "/")
        basename = (
            PureWindowsPath(target_path).name
            if WINDOWS_PATH_RE.match(target_path)
            else PurePosixPath(target_path).name
        ).lower()

        contains_display_verb = lowered.startswith(SHELL_FILE_READ_PREFIXES) or any(
            marker in lowered for marker in (' get-content ', ' cat ', ' type ', ' more ', '| cat', '| type')
        )
        if not contains_display_verb:
            return False

        normalized_command = lowered.replace("\\", "/")
        return normalized_target in normalized_command or (basename and basename in lowered)

    def _normalize_action_for_host_contract(
        self,
        state: RuntimeV2State,
        action: RuntimeV2Action,
    ) -> RuntimeV2Action:
        if action.type != "act" or action.tool != "shell":
            return action

        explicit_path = self._resolve_explicit_analyze_path(state)
        if not explicit_path:
            return action

        command = str((action.input or {}).get("command") or "").strip()
        if not self._looks_like_shell_file_display(command, explicit_path):
            return action

        normalized_raw = dict(action.raw or {})
        normalized_raw["host_normalization"] = {
            "kind": "explicit_path_analyze_promoted_to_file_read",
            "reason": "explicit file analyze requests must use file read, not shell display commands",
            "original_action": action.raw or {
                "type": action.type,
                "tool": action.tool,
                "input": dict(action.input or {}),
            },
            "resolved_path": explicit_path,
        }

        return RuntimeV2Action(
            type=action.type,
            goal=action.goal,
            steps=list(action.steps or []),
            tool="file",
            input={"operation": "read", "path": explicit_path},
            question=action.question,
            summary=action.summary,
            verification=dict(action.verification or {}),
            message=action.message,
            raw=normalized_raw,
        )

    def reset_session(self, session_id: str, *, command: str = "reset_session") -> RuntimeV2State:
        """
        重置 session，递增 generation_id 隔离旧消息。

        WS-1: 使用 increment_generation() 而不是直接创建新 state
        """
        if session_id in self._states:
            state = self._states[session_id]
            state.increment_generation()
            # 清空 history 和 pending_artifacts
            state.history = []
            state.pending_artifacts = []
            state.last_uploaded_artifact = None
            state.last_explicit_target = None
            state.last_inferred_action = None
            state.pending_bundle_summary = None
            if self.proto_self_adapter is not None and hasattr(self.proto_self_adapter, "state_store"):
                try:
                    self.proto_self_adapter.state_store.record_session_reset(
                        session_id=session_id,
                        thread_id=session_id,
                        source="runtime_v2",
                        command=command,
                        generation_id=state.generation_id,
                    )
                except Exception as exc:
                    logger.warning(f"[PSK-RESET] Failed to record session reset for {session_id}: {exc}")
            return state
        else:
            self._states[session_id] = RuntimeV2State(session_id=session_id)
            if self.proto_self_adapter is not None and hasattr(self.proto_self_adapter, "state_store"):
                try:
                    self.proto_self_adapter.state_store.record_session_reset(
                        session_id=session_id,
                        thread_id=session_id,
                        source="runtime_v2",
                        command=command,
                        generation_id=self._states[session_id].generation_id,
                    )
                except Exception as exc:
                    logger.warning(f"[PSK-RESET] Failed to record initial session reset for {session_id}: {exc}")
            return self._states[session_id]

    async def run_turn_typed(
        self,
        session_id: str,
        user_input: str,
        max_steps: int = 6,
        *,
        source: str = "telegram",
        evidence_collector: Optional[Any] = None,
        progress_callback: Optional[Callable[[ProgressEvent], Awaitable[None]]] = None,
        run_event_callback: Optional[Callable[[RunEvent], Awaitable[None]]] = None,
    ) -> RuntimeV2TurnResult:
        logger.info(f"[PSK-TG-TRACE-01] run_turn_typed called session_id={session_id}, user_input={user_input[:50]}...")
        state = self.get_state(session_id)
        if not state.task_id:
            state.task_id = f"task_{uuid.uuid4().hex[:8]}"

        # WS-1: 开始新 turn
        turn_id = state.start_turn()
        generation_id = state.generation_id
        logger.info(f"[PSK-TG-TRACE-02] turn started turn_id={turn_id}")

        # 截断后再存储，防止文件内容进入 state
        truncated_input = _truncate_user_input(user_input)
        state.clear_pending_proactive_followup()
        state.last_user_turn = truncated_input
        state.record("user", {"text": truncated_input})

        # Proto-Self Kernel: 在决策前调用，注入主体倾向
        logger.info(f"[PSK-TG-TRACE-03] proto_self_adapter={self.proto_self_adapter is not None}")
        if self.proto_self_runtime:
            try:
                logger.info(f"[PSK-TG-TRACE-04] Processing proto-self ingress for {session_id}_{turn_id}")
                self.proto_self_runtime.process_ingress(
                    session_id=session_id,
                    turn_id=turn_id,
                    source=source,
                    user_input=truncated_input,
                    state=state,
                    evidence_collector=evidence_collector,
                )
                logger.info(f"[PSK-TG-TRACE-10] Proto-Self processing completed")
            except Exception as e:
                # Proto-Self Kernel 失败不影响主流程
                logger.error(f"[PSK-TG-TRACE-ERROR] {e}")
                state.record("proto_self", {"error": str(e)})

        return await self._advance_turn(
            session_id=session_id,
            state=state,
            max_steps=max_steps,
            source=source,
            evidence_collector=evidence_collector,
            turn_id=turn_id,
            generation_id=generation_id,
            progress_callback=progress_callback,
            run_event_callback=run_event_callback,
        )

    async def continue_turn_typed(
        self,
        session_id: str,
        *,
        max_steps: int = 6,
        source: str = "autonomy",
        evidence_collector: Optional[Any] = None,
        state: Optional[RuntimeV2State] = None,
        progress_callback: Optional[Callable[[ProgressEvent], Awaitable[None]]] = None,
        run_event_callback: Optional[Callable[[RunEvent], Awaitable[None]]] = None,
    ) -> RuntimeV2TurnResult:
        state = state or self.get_state(session_id)
        if not state.task_id:
            state.task_id = f"task_{uuid.uuid4().hex[:8]}"
        if not state.active_turn_id:
            turn_id = state.start_turn()
        else:
            turn_id = state.active_turn_id
            state.active_turn_status = "running"
            state.final_sent = False
        generation_id = state.generation_id
        return await self._advance_turn(
            session_id=session_id,
            state=state,
            max_steps=max_steps,
            source=source,
            evidence_collector=evidence_collector,
            turn_id=turn_id,
            generation_id=generation_id,
            progress_callback=progress_callback,
            run_event_callback=run_event_callback,
        )

    async def _advance_turn(
        self,
        *,
        session_id: str,
        state: RuntimeV2State,
        max_steps: int,
        source: str,
        evidence_collector: Optional[Any],
        turn_id: str,
        generation_id: int,
        progress_callback: Optional[Callable[[ProgressEvent], Awaitable[None]]],
        run_event_callback: Optional[Callable[[RunEvent], Awaitable[None]]],
    ) -> RuntimeV2TurnResult:
        if str(((state.ingress_context or {}).get("interaction_kind") or "")).strip() == "chat":
            result = await self.chat_reply_engine.reply(state)
            if result.reply:
                result.reply.generation_id = generation_id
                result.reply.turn_id = turn_id
            self._capture_proto_self_response_plan(result=result, evidence_collector=evidence_collector)
            return result

        blocked_result = await self._promote_host_owned_frontier(
            state=state,
            run_event_callback=run_event_callback,
            generation_id=generation_id,
            turn_id=turn_id,
        )
        if blocked_result is not None:
            return blocked_result
        invalid_json_retries = 0
        for step in range(max_steps):
            action = await self._decide(state)
            action = self._normalize_action_for_host_contract(state, action)
            state.last_model_action = action.raw
            state.record("assistant", action.raw)

            if action.type == "ask" and action.raw.get("kind") in {"invalid_json", "invalid_type"}:
                invalid_json_retries += 1
                state.record("system", {"retry_reason": action.raw.get("kind")})
                if invalid_json_retries <= 1:
                    continue
                state.task_status = "resumable_pause"
                return RuntimeV2TurnResult(
                    status="resumable_pause",
                    state=state,
                    reply=RuntimeV2Reply(
                        reply_text="",
                        delivery_kind="progress",
                        status="resumable_pause",
                        suppressible=True,
                        generation_id=generation_id,
                        turn_id=turn_id,
                    ),
                    finish_reason="invalid_json_retry_exhausted",
                    checkpoint_payload={"state_snapshot": state.to_snapshot()},
                )

            if action.type == "ask" and action.raw.get("kind") == "transient_decision_error":
                state.record(
                    "system",
                    {
                        "retry_reason": "transient_decision_error",
                        "error": action.raw.get("error"),
                        "error_class": action.raw.get("error_class"),
                        "status_code": action.raw.get("status_code"),
                    },
                )
                state.task_status = "resumable_pause"
                state.waiting_for_user_input = False
                return RuntimeV2TurnResult(
                    status="resumable_pause",
                    state=state,
                    reply=RuntimeV2Reply(
                        reply_text="",
                        delivery_kind="progress",
                        status="resumable_pause",
                        suppressible=True,
                        generation_id=generation_id,
                        turn_id=turn_id,
                    ),
                    finish_reason="transient_decision_error",
                    checkpoint_payload={"state_snapshot": state.to_snapshot()},
                )

            transition = await self.transition_engine.apply(state, action)
            blocked_result = await self._promote_host_owned_frontier(
                state=state,
                run_event_callback=run_event_callback,
                generation_id=generation_id,
                turn_id=turn_id,
            )
            if blocked_result is not None:
                return blocked_result
            await self._emit_progress_events(state, progress_callback)

            if self.proto_self_runtime and action.type == "act" and state.last_tool_result:
                try:
                    self.proto_self_runtime.process_external_result(
                        session_id=session_id,
                        turn_id=turn_id,
                        step=step,
                        state=state,
                        evidence_collector=evidence_collector,
                    )
                except Exception as e:
                    state.record("proto_self", {"external_result_error": str(e)})

            if transition.get("done"):
                result = transition["result"]
                if not isinstance(result, RuntimeV2TurnResult):
                    raise TypeError(f"Runtime v2 transition must return RuntimeV2TurnResult, got {type(result)!r}")
                if result.reply:
                    result.reply.generation_id = generation_id
                    result.reply.turn_id = turn_id

                if self.proto_self_runtime:
                    self._capture_proto_self_response_plan(result=result, evidence_collector=evidence_collector)

                return result

        blocked_result = await self._promote_host_owned_frontier(
            state=state,
            run_event_callback=run_event_callback,
            generation_id=generation_id,
            turn_id=turn_id,
        )
        if blocked_result is not None:
            return blocked_result

        state.task_status = "resumable_pause"
        return RuntimeV2TurnResult(
            status="resumable_pause",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="",
                delivery_kind="progress",
                status="resumable_pause",
                suppressible=True,
                generation_id=generation_id,
                turn_id=turn_id,
            ),
            finish_reason="max_steps_exhausted",
            checkpoint_payload={"state_snapshot": state.to_snapshot()},
        )

    async def _decide(self, state: RuntimeV2State) -> RuntimeV2Action:
        return await self.decision_engine.decide(state)

    def _capture_proto_self_response_plan(self, *, result: RuntimeV2TurnResult, evidence_collector: Optional[Any]) -> None:
        if not self.proto_self_runtime:
            return
        try:
            self.proto_self_runtime.capture_response_plan(
                result=result,
                evidence_collector=evidence_collector,
            )
            logger.info(f"[E4-EVIDENCE] Captured response_plan: status={result.status}")
        except Exception as e:
            logger.warning(f"[E4-EVIDENCE] Failed to capture response_plan: {e}")

    async def _emit_progress_events(
        self,
        state: RuntimeV2State,
        progress_callback: Optional[Callable[[ProgressEvent], Awaitable[None]]],
    ) -> None:
        if progress_callback is None or not state.has_pending_progress_events():
            return
        events = state.pop_progress_events()
        for event in events:
            if not isinstance(event, ProgressEvent):
                continue
            if is_terminal_event(event.event_type):
                state.push_progress_event(event)
                continue
            await progress_callback(event)

    async def _emit_run_events(
        self,
        state: RuntimeV2State,
        run_event_callback: Optional[Callable[[RunEvent], Awaitable[None]]],
    ) -> None:
        if run_event_callback is None or not getattr(state, "has_pending_run_events", lambda: False)():
            return
        for event in state.pop_run_events():
            await run_event_callback(event)

    async def _promote_host_owned_frontier(
        self,
        *,
        state: RuntimeV2State,
        run_event_callback: Optional[Callable[[RunEvent], Awaitable[None]]],
        generation_id: int,
        turn_id: str,
    ) -> Optional[RuntimeV2TurnResult]:
        if not hasattr(state, "get_run_items") or not state.get_run_items():
            return None

        state.ensure_active_run_item_started()
        promotion = state.advance_run_item_frontier()
        await self._emit_run_events(state, run_event_callback)

        if not promotion.get("blocked"):
            return None

        verification = promotion.get("verification_result") or state.last_verification_result or {}
        state.task_status = "blocked"
        state.waiting_for_user_input = False
        state.last_delivery_type = "blocked"
        return RuntimeV2TurnResult(
            status="blocked",
            state=state,
            reply=RuntimeV2Reply(
                reply_text=_build_host_blocked_summary(state, verification),
                delivery_kind="final",
                status="blocked",
                generation_id=generation_id,
                turn_id=turn_id,
            ),
            finish_reason=verification.get("reason") or "blocked_current_item",
            checkpoint_payload={"state_snapshot": state.to_snapshot()},
        )
