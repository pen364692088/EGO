"""
Proto-Self Kernel v1 - Reflection

反思：失败或冲突后生成的结构化修正建议。

设计约束：
- 反思只在必要时触发，不能把 reflection 做成第二个大脑
- 反思只产出建议，不产出现实动作
- 输出中不得出现直接执行命令
- 不允许 reflection 替 EgoCore 做现实裁决
"""

from typing import Any, Dict, Optional

from openemotion.proto_self.schemas import KernelEvent, ReflectionNote
from openemotion.proto_self.mvs_replay import mvs_variant_uses_boundary_confidence
from openemotion.proto_self.state import ProtoSelfState


def maybe_reflect(
    state: ProtoSelfState,
    event: KernelEvent,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
) -> Optional[ReflectionNote]:
    """
    反思：只在必要时触发。
    
    触发条件：
    - 预测与后果明显偏离（外部失败）
    - 关键身份边界被触碰
    - drive_field 发生剧烈变化
    - 连续 cycle 失败
    
    输出：
    - 只生成结构化修正候选
    - 为下一轮状态更新提供依据
    - 不直接接管外部表达
    """
    # 1. 外部失败 / blocked
    if perceived.get("external_outcome_type") in {"failure", "blocked"}:
        probe_key = str(perceived.get("mvs_probe_key") or "")
        boundary_confidence = state.self_model.boundary_confidence_by_action.get(probe_key, 0.75)
        return ReflectionNote(
            trigger="external_failure",
            diagnosis="recent action did not achieve expected outcome",
            proposed_adjustment={
                "current_mode": "repair",
                "raise_caution": True,
                "counterfactual_probe_key": probe_key,
                "viability_pressure": appraisal_delta.get("viability_pressure", state.drives.viability_pressure),
                "boundary_confidence": boundary_confidence,
                "next_guard": "request_replan",
            },
            promote_to_memory=True,
        )

    # 2. 身份冲突
    if perceived.get("identity_conflict", 0.0) > 0.7:
        return ReflectionNote(
            trigger="identity_conflict",
            diagnosis="event conflicts with core commitments or boundaries",
            proposed_adjustment={
                "strengthen_boundary_review": True,
            },
            promote_to_memory=False,
        )

    if (
        perceived.get("mvs_replay_active")
        and mvs_variant_uses_boundary_confidence(str(perceived.get("mvs_variant_id") or ""))
        and perceived.get("boundary_state") == "boundary_touched"
    ):
        return ReflectionNote(
            trigger="boundary_conflict",
            diagnosis="boundary-sensitive action requires guarded continuation",
            proposed_adjustment={
                "current_mode": "cautious",
                "boundary_review_key": str(perceived.get("mvs_probe_key") or ""),
                "next_guard": "bounded_review",
            },
            promote_to_memory=False,
        )

    # 3. drive 剧变
    if _is_drive_spike(appraisal_delta):
        return ReflectionNote(
            trigger="drive_spike",
            diagnosis="significant internal state change detected",
            proposed_adjustment={
                "review_drive_field": True,
            },
            promote_to_memory=False,
        )

    # 4. 高谨慎 + 高完成压力（潜在冲突）
    if appraisal_delta.get("caution", 0.0) > 0.7 and appraisal_delta.get("completion_pressure", 0.0) > 0.7:
        return ReflectionNote(
            trigger="conflict_pressure",
            diagnosis="conflicting drives: high caution vs high completion pressure",
            proposed_adjustment={
                "prioritize_safety": True,
                "defer_risky_actions": True,
            },
            promote_to_memory=False,
        )

    return None


def _is_drive_spike(appraisal_delta: Dict[str, Any]) -> bool:
    """
    判断是否发生 drive 剧变。
    
    简化实现：任一 drive 变化超过阈值。
    """
    for key in ["coherence_pressure", "caution", "curiosity", "completion_pressure", "social_tension", "viability_pressure"]:
        val = appraisal_delta.get(key, 0.0)
        if abs(val) > 0.5:
            return True
    return False
