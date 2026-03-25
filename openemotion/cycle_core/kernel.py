"""
Cycle Core Kernel - 循环主体核核心调度器

职责: 唯一核心调度器，实现完整的循环流程

流程:
1. ingest structured event
2. load current self state
3. compute salience
4. run memory gate
5. generate consolidation candidates
6. update self state
7. decode readout
8. produce result_v1

设计原则:
- 单入口
- 单出口
- 有 trace/debug 信息
- 可 replay

版本: v1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import json
import uuid

# 导入内部模块
from openemotion.cycle_core.state import LatentSelfState
from openemotion.memory.salience import SalienceEvaluator, SalienceBreakdown
from openemotion.cycle_core.memory_gate import MemoryGate, MemoryGateResult, MemoryWriteDecision
from openemotion.memory.consolidation import Consolidator, ConsolidationResult
from openemotion.cycle_core.readout import ReadoutDecoder, ReadoutResult

# 导入结果类型
from openemotion.contracts.result_v1 import (
    OpenEmotionResultV1,
    ResultType,
    SelfModelDelta,
    MemoryUpdate,
    PolicyHint,
    ResponseTendency,
    Stability,
    Error,
)


@dataclass
class CycleTrace:
    """
    循环追踪记录

    用于调试和 replay
    """
    trace_id: str
    event_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # 各阶段结果
    salience_result: Optional[dict] = None
    memory_gate_result: Optional[dict] = None
    consolidation_result: Optional[dict] = None
    state_before: Optional[dict] = None
    state_after: Optional[dict] = None
    readout_result: Optional[dict] = None

    # 性能指标
    processing_time_ms: float = 0.0

    # 错误信息
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "salience_result": self.salience_result,
            "memory_gate_result": self.memory_gate_result,
            "consolidation_result": self.consolidation_result,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "readout_result": self.readout_result,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "error": self.error,
        }


class CycleCoreKernel:
    """
    循环主体核核心调度器

    职责: 实现 event -> state update -> memory gate -> readout 的完整循环
    """

    def __init__(
        self,
        salience_evaluator: Optional[SalienceEvaluator] = None,
        memory_gate: Optional[MemoryGate] = None,
        consolidator: Optional[Consolidator] = None,
        readout_decoder: Optional[ReadoutDecoder] = None,
    ):
        # 组件注入
        self.salience_evaluator = salience_evaluator or SalienceEvaluator()
        self.memory_gate = memory_gate or MemoryGate()
        self.consolidator = consolidator or Consolidator()
        self.readout_decoder = readout_decoder or ReadoutDecoder()

        # 状态存储（简化实现，实际应持久化）
        self.states: dict[str, LatentSelfState] = {}

        # 追踪记录
        self.traces: dict[str, CycleTrace] = {}

        # 统计
        self.total_cycles = 0
        self.error_count = 0

    def process(
        self,
        event_dict: dict[str, Any],
        user_id: Optional[str] = None,
        state_id: Optional[str] = None,
    ) -> tuple[OpenEmotionResultV1, CycleTrace]:
        """
        处理事件（单入口）

        Args:
            event_dict: 标准化事件字典（符合 openemotion_event_v1 schema）
            user_id: 用户ID（用于状态隔离）
            state_id: 状态ID（可选，默认用 user_id）

        Returns:
            tuple[OpenEmotionResultV1, CycleTrace]: 结果和追踪记录
        """
        start_time = datetime.now(timezone.utc)
        trace_id = f"trace_{uuid.uuid4().hex[:16]}"
        event_id = event_dict.get("event_id", "unknown")

        trace = CycleTrace(
            trace_id=trace_id,
            event_id=event_id,
        )

        try:
            # 1. 加载或创建状态
            state_key = state_id or user_id or "default"
            current_state = self._load_state(state_key)
            
            # 捕获更新前的状态（用于 old_value）
            old_affective_tension = current_state.affective_tension.to_dict() if hasattr(current_state, 'affective_tension') else None
            
            trace.state_before = current_state.to_dict()

            # 2. 计算重要性
            salience_breakdown = self._compute_salience(event_dict, current_state)
            trace.salience_result = salience_breakdown.to_dict()

            # 3. 记忆门决策
            memory_gate_result = self._run_memory_gate(
                event_dict, current_state, salience_breakdown
            )
            trace.memory_gate_result = memory_gate_result.to_dict()

            # 4. 记忆整合
            consolidation_result = self._consolidate(
                event_dict, current_state, memory_gate_result
            )
            trace.consolidation_result = consolidation_result.to_dict()

            # 5. 更新状态
            self._update_state(
                event_dict, current_state, salience_breakdown, consolidation_result
            )
            trace.state_after = current_state.to_dict()

            # 6. 解码输出
            readout_result = self._decode_readout(
                current_state, event_dict, consolidation_result
            )
            trace.readout_result = readout_result.to_dict()

            # 7. 生成结果
            result = self._produce_result(
                event_id, current_state, memory_gate_result, readout_result,
                old_affective_tension
            )

            # 8. 保存状态
            self._save_state(state_key, current_state)

            # 记录追踪
            trace.processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.traces[trace_id] = trace
            self.total_cycles += 1

            return result, trace

        except Exception as e:
            trace.error = str(e)
            trace.processing_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.traces[trace_id] = trace
            self.error_count += 1

            # 返回错误结果
            error_result = OpenEmotionResultV1(
                event_id=event_id,
                result_type=ResultType.ERROR,
                confidence=0.0,
                error=Error(
                    code="CYCLE_ERROR",
                    message=str(e),
                    recoverable=True,
                ),
            )

            return error_result, trace

    def _load_state(self, state_key: str) -> LatentSelfState:
        """加载状态"""
        if state_key in self.states:
            return self.states[state_key]
        return LatentSelfState()

    def _save_state(self, state_key: str, state: LatentSelfState):
        """保存状态"""
        self.states[state_key] = state

    def _compute_salience(
        self,
        event_dict: dict[str, Any],
        current_state: LatentSelfState,
    ) -> SalienceBreakdown:
        """计算事件重要性"""
        return self.salience_evaluator.evaluate(
            event_type=event_dict.get("event_type", "unknown"),
            event_content=event_dict.get("content", ""),
            current_state=current_state,
            event_metadata=event_dict.get("metadata"),
        )

    def _run_memory_gate(
        self,
        event_dict: dict[str, Any],
        current_state: LatentSelfState,
        salience_breakdown: SalienceBreakdown,
    ) -> MemoryGateResult:
        """运行记忆门"""
        return self.memory_gate.decide(
            salience_breakdown=salience_breakdown,
            event_type=event_dict.get("event_type", "unknown"),
            current_state=current_state,
            event_metadata=event_dict.get("metadata"),
        )

    def _consolidate(
        self,
        event_dict: dict[str, Any],
        current_state: LatentSelfState,
        memory_gate_result: MemoryGateResult,
    ) -> ConsolidationResult:
        """记忆整合"""
        return self.consolidator.consolidate(
            event_dict=event_dict,
            current_state=current_state,
            memory_gate_result=memory_gate_result,
        )

    def _update_state(
        self,
        event_dict: dict[str, Any],
        current_state: LatentSelfState,
        salience_breakdown: SalienceBreakdown,
        consolidation_result: ConsolidationResult,
    ):
        """
        更新自我状态

        这是循环的核心：状态变化会影响后续输出
        """
        event_type = event_dict.get("event_type", "unknown")
        event_content = event_dict.get("content", "")
        user_id = event_dict.get("actor", "")

        # 1. 更新情感张力
        self._update_affective_tension(
            current_state, event_type, event_content, salience_breakdown
        )

        # 2. 更新目标激活
        self._update_goal_activation(
            current_state, event_type, event_content, salience_breakdown
        )

        # 3. 更新关系偏向
        if user_id:
            self._update_relation_bias(
                current_state, user_id, event_type, event_content
            )

        # 4. 应用整合结果
        self._apply_consolidation(current_state, consolidation_result)

    def _update_affective_tension(
        self,
        state: LatentSelfState,
        event_type: str,
        event_content: str,
        salience: SalienceBreakdown,
    ):
        """更新情感张力"""
        # 基于事件类型推断效价变化
        valence_delta = 0.0
        arousal_delta = 0.0

        # 正面事件
        positive_markers = ["谢谢", "好", "成功", "完成", "棒", "喜欢"]
        for marker in positive_markers:
            if marker in event_content:
                valence_delta += 0.2
                arousal_delta += 0.1

        # 负面事件
        negative_markers = ["错", "失败", "问题", "不行", "不好", "糟糕"]
        for marker in negative_markers:
            if marker in event_content:
                valence_delta -= 0.2
                arousal_delta += 0.15

        # 高重要性事件增强影响
        if salience.compute_weighted_score() > 0.6:
            valence_delta *= 1.5
            arousal_delta *= 1.5

        state.update_affective_tension(valence_delta, arousal_delta)

    def _update_goal_activation(
        self,
        state: LatentSelfState,
        event_type: str,
        event_content: str,
        salience: SalienceBreakdown,
    ):
        """更新目标激活"""
        # 任务完成 -> 降低激活
        if event_type == "task_complete":
            # 降低相关目标激活
            for goal in state.goals.values():
                if salience.goal_relevance > 0.5:
                    state.update_goal(
                        goal_id=goal.goal_id,
                        description=goal.description,
                        delta_activation=-0.1,
                        delta_progress=0.2,
                    )

        # 用户提到目标相关 -> 增加激活
        if salience.goal_relevance > 0.6:
            # 激活相关目标
            for goal in state.goals.values():
                if any(kw in event_content for kw in goal.description.split()[:3]):
                    state.update_goal(
                        goal_id=goal.goal_id,
                        description=goal.description,
                        delta_activation=0.1,
                    )

    def _update_relation_bias(
        self,
        state: LatentSelfState,
        user_id: str,
        event_type: str,
        event_content: str,
    ):
        """更新关系偏向"""
        # 判断是否正面互动
        positive = any(kw in event_content for kw in ["谢谢", "好的", "喜欢", "棒"])
        negative = any(kw in event_content for kw in ["不好", "错", "问题", "不行"])

        if positive:
            state.update_relation_bias(user_id, positive=True, impact=0.1)
        elif negative:
            state.update_relation_bias(user_id, positive=False, impact=0.15)

    def _apply_consolidation(
        self,
        state: LatentSelfState,
        consolidation_result: ConsolidationResult,
    ):
        """应用整合结果"""
        # 从策略候选更新约束
        for policy in consolidation_result.policy_candidates:
            if policy.confidence > 0.6 and policy.policy_type == "constraint":
                state.update_constraint(
                    constraint_id=policy.name,
                    description=policy.description,
                    activation=policy.confidence,
                    strictness=0.7,
                    source=policy.source_type,
                )

    def _decode_readout(
        self,
        current_state: LatentSelfState,
        event_dict: dict[str, Any],
        consolidation_result: ConsolidationResult,
    ) -> ReadoutResult:
        """解码输出"""
        return self.readout_decoder.decode(
            current_state=current_state,
            event_dict=event_dict,
            consolidation_result=consolidation_result,
        )

    def _produce_result(
        self,
        event_id: str,
        current_state: LatentSelfState,
        memory_gate_result: MemoryGateResult,
        readout_result: ReadoutResult,
        old_affective_tension: Optional[dict] = None,
    ) -> OpenEmotionResultV1:
        """
        生成最终结果

        这是单出口
        """
        # 构建 self_model_delta
        self_model_delta = None
        state_before = memory_gate_result.salience_score
        # 简化：用情感张力变化表示 self_model 变化
        if hasattr(current_state, 'affective_tension'):
            self_model_delta = SelfModelDelta(
                field="affective_tension",
                old_value=old_affective_tension,  # 使用捕获的更新前状态
                new_value=current_state.affective_tension.to_dict(),
                reason="事件处理导致状态变化",
            )

        # 构建 memory_update
        memory_update = MemoryUpdate(
            event_stored=memory_gate_result.event_layer,
            narrative_created=memory_gate_result.narrative_candidate,
            policy_candidate=memory_gate_result.policy_candidate,
            salience_score=memory_gate_result.salience_score,
        )

        # 构建 policy_hint
        policy_hint = None
        if readout_result.policy_hint:
            policy_hint = PolicyHint(
                hint_type=readout_result.policy_hint.hint_type,
                reason=readout_result.policy_hint.reason,
                confidence=readout_result.policy_hint.confidence,
            )

        # 构建 response_tendency
        # 注意：这里使用 contracts 中的类型，需要转换
        from openemotion.contracts.result_v1 import ResponseTone as ContractTone, ResponseLength as ContractLength

        # 从 readout 的 enum 转换到 contracts 的 enum
        tone_mapping = {
            "warm": ContractTone.WARM,
            "neutral": ContractTone.NEUTRAL,
            "guarded": ContractTone.GUARDED,
            "apologetic": ContractTone.APOLOGETIC,
            "enthusiastic": ContractTone.ENTHUSIASTIC,
            "cautious": ContractTone.CAUTIOUS,
        }
        length_mapping = {
            "brief": ContractLength.BRIEF,
            "moderate": ContractLength.MODERATE,
            "detailed": ContractLength.DETAILED,
        }

        response_tendency = ResponseTendency(
            tone=tone_mapping.get(readout_result.response_tendency.tone.value, ContractTone.NEUTRAL),
            length=length_mapping.get(readout_result.response_tendency.length.value, ContractLength.MODERATE),
            urgency=readout_result.response_tendency.urgency,
        )

        # 构建稳定性
        stability = Stability(
            self_model_stable=current_state.stability.overall_stability > 0.5,
            memory_integrity=True,
            policy_consistent=current_state.stability.consistency > 0.7,
        )

        return OpenEmotionResultV1(
            event_id=event_id,
            result_type=ResultType.INTERPRETATION,
            confidence=readout_result.overall_confidence,
            self_model_delta=self_model_delta,
            memory_update=memory_update,
            policy_hint=policy_hint,
            response_tendency=response_tendency,
            stability=stability,
        )

    def get_trace(self, trace_id: str) -> Optional[CycleTrace]:
        """获取追踪记录"""
        return self.traces.get(trace_id)

    def get_state(self, state_key: str) -> Optional[LatentSelfState]:
        """获取状态"""
        return self.states.get(state_key)

    def replay(self, trace_id: str) -> Optional[OpenEmotionResultV1]:
        """
        重放追踪

        用于调试和验证
        """
        trace = self.get_trace(trace_id)
        if not trace or not trace.state_before:
            return None

        # 从 state_before 重建状态
        # 简化实现：实际需要完整序列化/反序列化
        # 这里只返回 trace 中记录的结果
        if trace.readout_result:
            # 从 trace 重建结果
            return OpenEmotionResultV1(
                event_id=trace.event_id,
                result_type=ResultType.INTERPRETATION,
                confidence=trace.readout_result.get("overall_confidence", 0.5),
            )

        return None

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_cycles": self.total_cycles,
            "error_count": self.error_count,
            "state_count": len(self.states),
            "trace_count": len(self.traces),
        }


# 默认实例
default_kernel = CycleCoreKernel()


# 版本标记
KERNEL_V1_VERSION = "1.0.0"
