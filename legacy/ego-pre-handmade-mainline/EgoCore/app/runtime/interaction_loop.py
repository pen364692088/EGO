"""
Interaction Loop - EgoCore 最小循环 Agent 主链

这是 W2 要求的"单会话、单模型、单循环"loop runtime。

核心规则：
1. LLM 每轮只能输出三类决定：reply, act, ask
2. 如果是 reply：直接回复用户
3. 如果是 act：走现有 task/tool runtime 执行
4. 执行结果必须结构化回流给 OpenEmotion
5. 必须设置循环上限：max_steps, max_repair, max_seconds
6. 禁止 LLM 直接自由输出任意 shell 文本

版本: v1.0.0
Created: 2026-03-19
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging

from .types import (
    EgoCoreRunParams,
    EgoCoreRunResult,
    RunStatus,
    LifecyclePhase,
    ReplyPayload,
    ReplyType,
)
from .event_bus import get_event_bus, emit_lifecycle_event, emit_reply_event

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_MAX_STEPS = 10
DEFAULT_MAX_REPAIR = 3
DEFAULT_MAX_SECONDS = 300  # 5 分钟

# 循环控制
LOOP_CONTROL_ENABLED = True


# =============================================================================
# Types
# =============================================================================

class LoopDecision(str, Enum):
    """循环决策类型"""
    REPLY = "reply"      # 直接回复
    ACT = "act"          # 执行动作
    ASK = "ask"          # 请求用户输入
    DONE = "done"        # 完成
    ERROR = "error"      # 错误


@dataclass
class LoopState:
    """循环状态"""
    turn_index: int = 0
    step_count: int = 0
    repair_count: int = 0
    total_tokens: int = 0
    
    # 决策历史
    decisions: List[LoopDecision] = field(default_factory=list)
    
    # 执行结果
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # OpenEmotion 状态
    self_model_delta: Optional[Dict[str, Any]] = None
    memory_update: Optional[Dict[str, Any]] = None
    policy_hint: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "step_count": self.step_count,
            "repair_count": self.repair_count,
            "total_tokens": self.total_tokens,
            "decisions": [d.value for d in self.decisions],
        }


@dataclass
class LoopConfig:
    """循环配置"""
    max_steps: int = DEFAULT_MAX_STEPS
    max_repair: int = DEFAULT_MAX_REPAIR
    max_seconds: int = DEFAULT_MAX_SECONDS
    
    # 开关
    enable_repair: bool = True
    enable_memory_feedback: bool = True
    
    # 超时
    cognition_timeout_ms: int = 5000
    tool_timeout_ms: int = 30000


# =============================================================================
# Interaction Loop
# =============================================================================

class InteractionLoop:
    """
    最小循环 Agent 主链
    
    执行流程：
    1. 接收用户输入
    2. 调用 OpenEmotion /cycle 获取主体解释
    3. 根据 runtime_route 决定下一步：reply / act / ask
    4. 如果是 act，调用工具执行
    5. 执行结果回流给 OpenEmotion
    6. 循环直到完成或达到上限
    """
    
    def __init__(
        self,
        config: Optional[LoopConfig] = None,
        on_reply: Optional[Callable[[str], Awaitable[None]]] = None,
        on_tool_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        self.config = config or LoopConfig()
        self.on_reply = on_reply
        self.on_tool_event = on_tool_event
        
        # 延迟加载
        self._subject_adapter = None
        self._task_runtime = None
        self._tool_registry = None
    
    @property
    def subject_adapter(self):
        """延迟加载 SubjectAdapter"""
        if self._subject_adapter is None:
            from app.openemotion.subject_adapter import get_subject_adapter
            self._subject_adapter = get_subject_adapter()
        return self._subject_adapter
    
    @property
    def task_runtime(self):
        """延迟加载 TaskRuntime"""
        if self._task_runtime is None:
            from app.runtime.task_runtime import TaskRuntime
            self._task_runtime = TaskRuntime()
        return self._task_runtime
    
    @property
    def tool_registry(self):
        """延迟加载工具注册表"""
        if self._tool_registry is None:
            from app.tools import get_registry
            self._tool_registry = get_registry()
        return self._tool_registry
    
    async def run(
        self,
        params: EgoCoreRunParams,
    ) -> EgoCoreRunResult:
        """
        运行交互循环
        
        Args:
            params: 运行参数
        
        Returns:
            EgoCoreRunResult
        """
        run_id = params.run_id
        session_id = params.session_id
        start_time = datetime.now(timezone.utc)
        
        # 初始化状态
        state = LoopState()
        result = EgoCoreRunResult(
            run_id=run_id,
            session_id=session_id,
            status=RunStatus.RUNNING,
            started_at=start_time,
        )
        
        # 获取 event bus
        event_bus = get_event_bus()
        
        try:
            # 发射生命周期事件
            emit_lifecycle_event(
                phase=LifecyclePhase.START,
                run_id=run_id,
                session_id=session_id,
            )
            
            # 主循环
            while True:
                # 检查上限
                if not self._check_limits(state, start_time):
                    logger.warning(
                        f"Loop limits reached: steps={state.step_count}, "
                        f"repairs={state.repair_count}, "
                        f"turns={state.turn_index}"
                    )
                    break
                
                # 步骤 1: 调用 OpenEmotion /cycle
                cognition_result = await self._run_cognition(
                    params=params,
                    state=state,
                )
                
                state.step_count += 1
                state.decisions.append(LoopDecision(cognition_result.get("decision", "reply")))
                
                # 提取结果
                decision = cognition_result.get("decision", "reply")
                reply_text = cognition_result.get("reply_text", "")
                
                # 保存 OpenEmotion 状态
                state.self_model_delta = cognition_result.get("self_model_delta")
                state.memory_update = cognition_result.get("memory_update")
                state.policy_hint = cognition_result.get("policy_hint")
                
                # 步骤 2: 根据决策执行
                if decision == LoopDecision.REPLY.value:
                    # 直接回复
                    result.reply_text = reply_text
                    result.primary_mode = cognition_result.get("primary_mode", "chat")
                    result.runtime_route = "reply"
                    break
                
                elif decision == LoopDecision.ACT.value:
                    # 执行动作
                    emit_lifecycle_event(
                        phase=LifecyclePhase.COGNITION_COMPLETE,
                        run_id=run_id,
                        session_id=session_id,
                        data={"decision": decision},
                    )
                    
                    tool_result = await self._execute_tool(
                        cognition_result=cognition_result,
                        state=state,
                    )
                    
                    state.tool_results.append(tool_result)
                    
                    if tool_result.get("success"):
                        # 成功，回流给 OpenEmotion
                        if self.config.enable_memory_feedback:
                            await self._feed_back_result(
                                params=params,
                                state=state,
                                tool_result=tool_result,
                            )
                        
                        # 继续循环，让 OpenEmotion 决定下一步
                        continue
                    else:
                        # 失败，检查是否可以修复
                        if self.config.enable_repair and state.repair_count < self.config.max_repair:
                            state.repair_count += 1
                            continue
                        else:
                            # 无法修复，返回错误
                            result.reply_text = f"执行失败：{tool_result.get('error', '未知错误')}"
                            result.runtime_route = "error"
                            break
                
                elif decision == LoopDecision.ASK.value:
                    # 请求用户输入
                    result.reply_text = reply_text
                    result.runtime_route = "ask"
                    break
                
                elif decision == LoopDecision.DONE.value:
                    # 完成
                    result.reply_text = reply_text
                    result.runtime_route = "done"
                    break
                
                else:
                    # 未知决策，默认回复
                    logger.warning(f"Unknown decision: {decision}")
                    result.reply_text = reply_text
                    break
            
            # 循环结束
            result.status = RunStatus.COMPLETED
            
        except asyncio.TimeoutError:
            result.status = RunStatus.TIMEOUT
            result.error = "Interaction loop timed out"
            logger.error(f"Loop timeout: run_id={run_id}")
        
        except Exception as e:
            result.status = RunStatus.FAILED
            result.error = str(e)
            logger.error(f"Loop error: {e}")
        
        finally:
            # 计算时长
            end_time = datetime.now(timezone.utc)
            result.ended_at = end_time
            result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # 发射结束事件
            emit_lifecycle_event(
                phase=LifecyclePhase.END,
                run_id=run_id,
                session_id=session_id,
                data={"status": result.status.value},
            )
        
        return result
    
    def _check_limits(self, state: LoopState, start_time: datetime) -> bool:
        """检查循环上限"""
        # 检查步数
        if state.step_count >= self.config.max_steps:
            return False
        
        # 检查修复次数
        if state.repair_count >= self.config.max_repair:
            return False
        
        # 检查时间
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        if elapsed >= self.config.max_seconds:
            return False
        
        return True
    
    async def _run_cognition(
        self,
        params: EgoCoreRunParams,
        state: LoopState,
    ) -> Dict[str, Any]:
        """
        调用 OpenEmotion /cycle
        
        Returns:
            {
                "decision": "reply" | "act" | "ask" | "done",
                "reply_text": str,
                "tool_calls": List[Dict],
                "self_model_delta": Dict,
                "memory_update": Dict,
                "policy_hint": Dict,
            }
        """
        from app.openemotion_adapter.event_builder import default_event_builder
        
        # 构建事件
        event_v1 = default_event_builder.build_from_user_message(
            user_id=params.user_id or "unknown",
            content=params.prompt,
            session_id=params.session_id,
            metadata={
                "turn_index": state.turn_index,
                "step_count": state.step_count,
                "repair_count": state.repair_count,
                "tool_results": state.tool_results[-3:] if state.tool_results else [],
            }
        )
        
        # 调用 /cycle
        try:
            cycle_result = self.subject_adapter.cycle(event_v1)
            
            # 解析结果
            result_data = cycle_result.get("result", {})
            
            # 提取决策
            runtime_route = result_data.get("runtime_route", "chat")
            decision = self._map_route_to_decision(runtime_route)
            
            # 提取回复（如果没有，生成默认回复）
            reply_text = result_data.get("outward_response", {}).get("reply_text", "")
            if not reply_text:
                # 根据响应倾向生成默认回复
                tendency = result_data.get("response_tendency", {})
                tone = tendency.get("tone", "neutral")
                urgency = tendency.get("urgency", 0.5)
                
                if decision == LoopDecision.REPLY.value:
                    # 简单回复场景
                    reply_text = "好的，我收到了你的消息。"
                elif decision == LoopDecision.ASK.value:
                    reply_text = "请告诉我更多信息。"
                elif decision == LoopDecision.DONE.value:
                    reply_text = "任务完成。"
                else:
                    reply_text = "好的。" 
            
            # 提取工具调用
            tool_calls = result_data.get("tool_calls", [])
            
            return {
                "decision": decision,
                "reply_text": reply_text,
                "tool_calls": tool_calls,
                "primary_mode": result_data.get("interaction_interpretation", {}).get("primary_mode", "chat"),
                "self_model_delta": result_data.get("self_model_delta"),
                "memory_update": result_data.get("memory_update"),
                "policy_hint": result_data.get("policy_hint"),
            }
        
        except Exception as e:
            logger.error(f"Cognition failed: {e}")
            return {
                "decision": LoopDecision.ERROR.value,
                "reply_text": "抱歉，我遇到了一些问题。请稍后再试。",
                "error": str(e),
            }
    
    def _map_route_to_decision(self, runtime_route: str) -> str:
        """将 runtime_route 映射到决策"""
        mapping = {
            "chat": LoopDecision.REPLY.value,
            "reply": LoopDecision.REPLY.value,
            "task": LoopDecision.ACT.value,
            "tool": LoopDecision.ACT.value,
            "ask": LoopDecision.ASK.value,
            "done": LoopDecision.DONE.value,
            "error": LoopDecision.ERROR.value,
        }
        return mapping.get(runtime_route, LoopDecision.REPLY.value)
    
    async def _execute_tool(
        self,
        cognition_result: Dict[str, Any],
        state: LoopState,
    ) -> Dict[str, Any]:
        """
        执行工具
        
        注意：工具执行必须经过 EgoCore 现有工具边界与高风险阻断。
        不允许 LLM 直接自由输出 shell 文本。
        """
        tool_calls = cognition_result.get("tool_calls", [])
        
        if not tool_calls:
            return {"success": False, "error": "No tool calls"}
        
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            
            # 发射工具事件
            if self.on_tool_event:
                await self.on_tool_event({
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "status": "start",
                })
            
            # 执行工具（通过安全边界）
            result = await self._safe_execute_tool(tool_name, tool_args)
            
            results.append(result)
            
            # 发射结束事件
            if self.on_tool_event:
                await self.on_tool_event({
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "status": "end" if result.get("success") else "error",
                    "output": result.get("output"),
                    "error": result.get("error"),
                })
        
        # 返回最后一个结果（或合并）
        return results[-1] if results else {"success": False, "error": "No results"}
    
    async def _safe_execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        安全执行工具
        
        经过 preflight 检查和高风险阻断。
        """
        from app.runtime.tool_doctor import run_preflight
        from app.runtime.guard import check_execution_guard
        
        # Preflight 检查
        preflight_result = await run_preflight(tool_name, tool_args)
        if not preflight_result.get("ok"):
            return {
                "success": False,
                "error": f"Preflight failed: {preflight_result.get('reason')}",
            }
        
        # 执行守卫检查
        guard_result = check_execution_guard(tool_name, tool_args)
        if not guard_result.get("allowed"):
            return {
                "success": False,
                "error": f"Guard blocked: {guard_result.get('reason')}",
            }
        
        # 执行工具
        try:
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                return {"success": False, "error": f"Tool not found: {tool_name}"}
            
            result = await tool.execute(**tool_args)
            
            return {
                "success": True,
                "output": result,
                "tool_name": tool_name,
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
            }
    
    async def _feed_back_result(
        self,
        params: EgoCoreRunParams,
        state: LoopState,
        tool_result: Dict[str, Any],
    ) -> None:
        """
        执行结果回流给 OpenEmotion
        
        让 OpenEmotion 知道发生了什么，以便更新记忆/状态。
        """
        from app.openemotion_adapter.event_builder import default_event_builder
        from egocore.contracts.openemotion_event_v1 import EventType
        
        # 构建外部结果事件
        event_v1 = default_event_builder.build_from_user_message(
            user_id=params.user_id or "unknown",
            content="",
            session_id=params.session_id,
            event_type=EventType.EXTERNAL_RESULT.value,
            metadata={
                "turn_index": state.turn_index,
                "tool_result": tool_result,
            }
        )
        
        # 调用 /cycle（不产生回复，只更新状态）
        try:
            self.subject_adapter.cycle(event_v1)
        except Exception as e:
            logger.warning(f"Feedback to OpenEmotion failed: {e}")


# =============================================================================
# 便捷函数
# =============================================================================

def create_interaction_loop(
    max_steps: int = DEFAULT_MAX_STEPS,
    max_repair: int = DEFAULT_MAX_REPAIR,
    max_seconds: int = DEFAULT_MAX_SECONDS,
    **kwargs,
) -> InteractionLoop:
    """创建交互循环实例"""
    config = LoopConfig(
        max_steps=max_steps,
        max_repair=max_repair,
        max_seconds=max_seconds,
    )
    return InteractionLoop(config=config, **kwargs)


async def run_interaction_loop(
    params: EgoCoreRunParams,
    **kwargs,
) -> EgoCoreRunResult:
    """便捷函数：运行交互循环"""
    loop = create_interaction_loop(**kwargs)
    return await loop.run(params)
