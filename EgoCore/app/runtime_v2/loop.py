from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from datetime import datetime

from .action_protocol import RuntimeV2Action
from .decision_engine import RuntimeV2DecisionEngine
from .runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from .state import RuntimeV2State
from .tool_broker import RuntimeV2ToolBroker
from .transition import RuntimeV2TransitionEngine
from .verifier import RuntimeV2Verifier
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

        invalid_json_retries = 0
        for step in range(max_steps):
            action = await self._decide(state)
            state.last_model_action = action.raw
            state.record("assistant", action.raw)

            if action.type == "ask" and action.raw.get("kind") in {"invalid_json", "invalid_type"}:
                invalid_json_retries += 1
                state.record("system", {"retry_reason": action.raw.get("kind")})
                if invalid_json_retries <= 1:
                    continue
                state.task_status = "waiting_input"
                # 不再发送 generic busy 文案，返回空回复
                return RuntimeV2TurnResult(
                    status="waiting_input",
                    state=state,
                    reply=RuntimeV2Reply(
                        reply_text="",  # 空回复，不发送 generic busy
                        delivery_kind="progress",
                        status="waiting_input",
                        suppressible=True,
                        generation_id=generation_id,
                        turn_id=turn_id,
                    ),
                )

            transition = await self.transition_engine.apply(state, action)

            # Proto-Self Kernel: 工具执行后回流 external_result
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
                    # Proto-Self Kernel 失败不影响主流程
                    state.record("proto_self", {"external_result_error": str(e)})

            if transition.get("done"):
                result = transition["result"]
                if not isinstance(result, RuntimeV2TurnResult):
                    raise TypeError(f"Runtime v2 transition must return RuntimeV2TurnResult, got {type(result)!r}")
                # WS-1: 注入 generation_id 和 turn_id
                if result.reply:
                    result.reply.generation_id = generation_id
                    result.reply.turn_id = turn_id

                # E4 Evidence: Capture response_plan
                if self.proto_self_runtime:
                    try:
                        self.proto_self_runtime.capture_response_plan(
                            result=result,
                            evidence_collector=evidence_collector,
                        )
                        logger.info(f"[E4-EVIDENCE] Captured response_plan: status={result.status}")
                    except Exception as e:
                        logger.warning(f"[E4-EVIDENCE] Failed to capture response_plan: {e}")

                return result

        state.task_status = "waiting_input"
        # 不再发送 generic busy 文案，返回空回复
        return RuntimeV2TurnResult(
            status="waiting_input",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="",  # 空回复，不发送 generic busy
                delivery_kind="progress",
                status="waiting_input",
                suppressible=True,
                generation_id=generation_id,
                turn_id=turn_id,
            ),
        )

    async def _decide(self, state: RuntimeV2State) -> RuntimeV2Action:
        return await self.decision_engine.decide(state)
