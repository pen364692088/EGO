"""
AgentEventBus - Agent 事件总线

参考 OpenClaw 的 emitAgentEvent()，提供生命周期/工具/回复事件分发。

版本: v2.0.0
Created: 2026-03-19
"""

import asyncio
import inspect
from typing import Dict, Any, Optional, Callable, Awaitable, List, Set
from datetime import datetime, timezone
from collections import defaultdict
import logging
import json

from .types import (
    ReplyType,
    LifecycleEvent, LifecyclePhase,
    ToolEvent,
    ReplyPayload,
    STREAM_LIFECYCLE, STREAM_TOOL, STREAM_REPLY,
)

logger = logging.getLogger(__name__)


class AgentEventBusImpl:
    """
    Agent 事件总线

    参考 OpenClaw 的 agent event stream:
    - lifecycle: start, end, error
    - tool: start, progress, end
    - assistant: streaming deltas
    - reply: final reply payloads

    支持订阅/发布模式，便于 UI/控制面/外部渠道监听。
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = defaultdict(list)
        self._run_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._event_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._max_history = 100

    def emit_lifecycle(self, event: LifecycleEvent) -> None:
        """
        发射生命周期事件

        类似 OpenClaw 的 emitAgentEvent({stream: "lifecycle", ...})
        """
        data = event.to_dict()
        data["stream"] = STREAM_LIFECYCLE

        logger.debug(
            f"AgentEventBus: lifecycle phase={event.phase.value} "
            f"run={event.run_id} session={event.session_id}"
        )

        self._emit(event.run_id, data)
        self._record_history(event.run_id, data)

    def emit_tool(self, event: ToolEvent) -> None:
        """
        发射工具事件

        类似 OpenClaw 的 tool stream events
        """
        data = event.to_dict()
        data["stream"] = STREAM_TOOL

        logger.debug(
            f"AgentEventBus: tool name={event.tool_name} status={event.status}"
        )

        self._emit_all(data)
        # 不记录工具事件历史，太占空间

    def emit_reply(self, payload: ReplyPayload) -> None:
        """
        发射回复事件

        类似 OpenClaw 的 assistant stream events
        """
        data = payload.to_dict()
        data["stream"] = STREAM_REPLY

        logger.debug(
            f"AgentEventBus: reply type={payload.type.value} "
            f"is_final={payload.is_final} run={payload.run_id}"
        )

        self._emit(payload.run_id, data)
        self._record_history(payload.run_id, data)

    def emit(
        self,
        run_id: str,
        stream: str,
        data: Dict[str, Any],
    ) -> None:
        """
        通用发射方法

        Args:
            run_id: 运行 ID
            stream: 流类型 (lifecycle/tool/reply)
            data: 事件数据
        """
        data["stream"] = stream
        data["run_id"] = run_id
        data["timestamp"] = datetime.now(timezone.utc).isoformat()

        self._emit(run_id, data)

        if stream in (STREAM_LIFECYCLE, STREAM_REPLY):
            self._record_history(run_id, data)

    def _emit(self, run_id: str, data: Dict[str, Any]) -> None:
        """发射到订阅者"""
        for callback in self._subscribers[run_id]:
            try:
                self._dispatch_callback(callback, data)
            except Exception as e:
                logger.error(f"AgentEventBus: subscriber error: {e}")

    def _emit_all(self, data: Dict[str, Any]) -> None:
        """发射到所有订阅者"""
        for run_id, callbacks in self._subscribers.items():
            for callback in callbacks:
                try:
                    self._dispatch_callback(callback, data)
                except Exception as e:
                    logger.error(f"AgentEventBus: subscriber error: {e}")

    def _dispatch_callback(self, callback: Callable[[Dict[str, Any]], Any], data: Dict[str, Any]) -> None:
        result = callback(data)
        if not inspect.isawaitable(result):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(result)
        else:
            loop.create_task(result)

    def _record_history(self, run_id: str, data: Dict[str, Any]) -> None:
        """记录事件历史"""
        history = self._event_history[run_id]
        history.append(data)

        # 限制历史大小
        if len(history) > self._max_history:
            self._event_history[run_id] = history[-self._max_history:]

    def subscribe(
        self,
        run_id: str,
        callback: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """
        订阅事件

        类似 OpenClaw 的 subscribeEmbeddedPiSession()
        """
        self._subscribers[run_id].append(callback)
        logger.debug(f"AgentEventBus: subscribed to run={run_id}")

    def emit_lifecycle_event(
        self,
        *,
        phase: LifecyclePhase,
        run_id: str,
        session_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.emit_lifecycle(
            LifecycleEvent(
                phase=phase,
                run_id=run_id,
                session_id=session_id,
                data=data or {},
            )
        )

    def unsubscribe(self, run_id: str) -> None:
        """取消订阅"""
        if run_id in self._subscribers:
            del self._subscribers[run_id]
        if run_id in self._event_history:
            del self._event_history[run_id]
        logger.debug(f"AgentEventBus: unsubscribed from run={run_id}")

    def get_history(
        self,
        run_id: str,
        stream: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取事件历史

        Args:
            run_id: 运行 ID
            stream: 过滤流类型
            limit: 限制数量
        """
        history = self._event_history.get(run_id, [])

        if stream:
            history = [e for e in history if e.get("stream") == stream]

        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_subscriptions": len(self._subscribers),
            "total_subscribers": sum(len(c) for c in self._subscribers.values()),
            "runs_with_history": len(self._event_history),
        }


# 全局实例
_event_bus: Optional[AgentEventBusImpl] = None


def get_event_bus() -> AgentEventBusImpl:
    """获取全局事件总线"""
    global _event_bus
    if _event_bus is None:
        _event_bus = AgentEventBusImpl()
    return _event_bus


def emit_lifecycle_event(
    phase: LifecyclePhase,
    run_id: str,
    session_id: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    便捷函数：发射生命周期事件
    """
    event = LifecycleEvent(
        phase=phase,
        run_id=run_id,
        session_id=session_id,
        data=data or {},
    )
    get_event_bus().emit_lifecycle(event)


def emit_tool_event(
    tool_name: str,
    tool_args: Dict[str, Any],
    status: str,
    output: Optional[str] = None,
    error: Optional[str] = None,
    duration_ms: int = 0,
) -> None:
    """
    便捷函数：发射工具事件
    """
    event = ToolEvent(
        tool_name=tool_name,
        tool_args=tool_args,
        status=status,
        output=output,
        error=error,
        duration_ms=duration_ms,
    )
    get_event_bus().emit_tool(event)


def emit_reply_event(
    content: str,
    run_id: str,
    session_id: str,
    is_final: bool = True,
    is_partial: bool = False,
    sequence: int = 0,
) -> None:
    """
    便捷函数：发射回复事件
    """
    payload = ReplyPayload(
        type=ReplyType.TEXT,
        content=content,
        run_id=run_id,
        session_id=session_id,
        is_final=is_final,
        is_partial=is_partial,
        sequence=sequence,
    )
    get_event_bus().emit_reply(payload)
