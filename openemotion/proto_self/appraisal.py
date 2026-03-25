"""
Proto-Self Kernel v1 - Appraisal

感知与 drive_field 更新。

设计约束：
- appraisal 是功能性偏置，不是情绪文案
- drive_field 必须真实影响 policy_hint 和 response_tendency
- 否则就只是伪情绪文本
"""

from typing import Any, Dict

from openemotion.proto_self.schemas import KernelEvent
from openemotion.proto_self.state import ProtoSelfState


def perceive_event(event: KernelEvent, state: ProtoSelfState) -> Dict[str, Any]:
    """
    感知：把事件压成最小可更新语义。
    
    不做大而全 NLU，只提取关键维度。
    """
    return {
        "intent": event.user_intent,
        "event_type": event.event_type,
        "source": event.source,
        "novelty": _score_novelty(event, state),
        "identity_conflict": _score_identity_conflict(event, state),
        "unfinished_commitment": _score_unfinished_commitment(event, state),
        "risk_signal": _score_risk(event.safety_context),
        "relational_mismatch": _score_relation_mismatch(event, state),
        "external_outcome_type": _classify_external_result(event.external_result),
    }


def update_drive_field(state: ProtoSelfState, perceived: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新 drive_field：功能性偏置，不是情绪文案。
    
    更新规则：
    - coherence_pressure += identity_conflict * 0.4
    - curiosity += novelty * 0.3 - uncertainty_overload * 0.2
    - caution += risk_signal * 0.5
    - completion_pressure += unfinished_commitment * 0.4
    - social_tension += relational_mismatch * 0.4
    """
    current = state.drives

    return {
        "coherence_pressure": _clamp(current.coherence_pressure + perceived["identity_conflict"] * 0.4),
        "curiosity": _clamp(current.curiosity + perceived["novelty"] * 0.3 - perceived["risk_signal"] * 0.1),
        "caution": _clamp(current.caution + perceived["risk_signal"] * 0.5),
        "completion_pressure": _clamp(current.completion_pressure + perceived["unfinished_commitment"] * 0.4),
        "social_tension": _clamp(current.social_tension + perceived["relational_mismatch"] * 0.4),
    }


# ============================================================================
# Scoring Functions
# ============================================================================

def _score_novelty(event: KernelEvent, state: ProtoSelfState) -> float:
    """
    评估事件新颖性。
    
    简化实现：基于事件类型和 source 判断。
    """
    # 新 source 或新事件类型 = 高新颖性
    if event.source not in ["telegram", "cli", "api"]:
        return 0.8
    
    if event.event_type in ["user_message", "tool_result"]:
        return 0.3
    
    if event.event_type == "system_event":
        return 0.1
    
    return 0.5


def _score_identity_conflict(event: KernelEvent, state: ProtoSelfState) -> float:
    """
    评估身份冲突程度。
    
    简化实现：检查 safety_context 和 user_intent 是否触及核心边界。
    """
    if not event.safety_context:
        return 0.0
    
    # 如果 safety_context 标记了风险，检查是否触及核心边界
    risk_level = event.safety_context.get("risk_level", 0.0)
    boundary_touched = event.safety_context.get("boundary_touched", False)
    
    if boundary_touched:
        return min(1.0, risk_level * 2.0)
    
    return risk_level * 0.5


def _score_unfinished_commitment(event: KernelEvent, state: ProtoSelfState) -> float:
    """
    评估未完成承诺压力。
    
    简化实现：基于 task_context 判断。
    """
    if not event.task_context:
        return 0.0
    
    pending_tasks = event.task_context.get("pending_tasks", 0)
    blocked_tasks = event.task_context.get("blocked_tasks", 0)
    
    return min(1.0, (pending_tasks * 0.1 + blocked_tasks * 0.2))


def _score_risk(safety_context: Dict[str, Any]) -> float:
    """
    评估风险信号。
    """
    if not safety_context:
        return 0.0
    
    return safety_context.get("risk_level", 0.0)


def _score_relation_mismatch(event: KernelEvent, state: ProtoSelfState) -> float:
    """
    评估关系不匹配程度。
    
    简化实现：基于 conversation_context 判断。
    """
    if not event.conversation_context:
        return 0.0
    
    # 检查是否有冲突信号
    conflict_detected = event.conversation_context.get("conflict_detected", False)
    negative_sentiment = event.conversation_context.get("negative_sentiment", 0.0)
    
    if conflict_detected:
        return min(1.0, 0.5 + negative_sentiment * 0.5)
    
    return negative_sentiment * 0.3


def _classify_external_result(external_result: Dict[str, Any] | None) -> str:
    """
    分类外部结果类型。
    
    返回：success / failure / neutral / none
    """
    if not external_result:
        return "none"
    
    success = external_result.get("success", None)
    if success is True:
        return "success"
    elif success is False:
        return "failure"
    
    return "neutral"


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    限制值在 [min_val, max_val] 范围内。
    """
    return max(min_val, min(max_val, value))
