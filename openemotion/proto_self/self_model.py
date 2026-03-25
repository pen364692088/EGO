"""
Proto-Self Kernel v1 - Self-Model Update

自我模型更新：最小可测更新，不做"人格大杂烩"。

设计约束：
- 只做最小可测更新
- 不做复杂人格系统
- 更新必须可追溯、可回放
"""

from typing import Any, Dict

from openemotion.proto_self.state import ProtoSelfState


def update_self_model(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    更新 self_model：最小可测更新。
    
    只在明确信号下才改变 current_focus 和 current_mode。
    """
    delta = {
        "capabilities": {},
        "limitations": {},
        "current_focus": None,
        "current_mode": None,
        "self_confidence_by_domain": {},
    }

    # 高风险 → 切换到 cautious 模式
    if perceived.get("risk_signal", 0.0) > 0.7:
        delta["current_mode"] = "cautious"

    # 高完成压力 → 聚焦于收尾
    if appraisal_delta.get("completion_pressure", 0.0) > 0.6:
        delta["current_focus"] = "closure"

    # 高好奇心 + 低风险 → 切换到探索模式
    if appraisal_delta.get("curiosity", 0.0) > 0.7 and perceived.get("risk_signal", 0.0) < 0.3:
        delta["current_mode"] = "exploration"

    # 外部失败 → 切换到修复模式
    if perceived.get("external_outcome_type") == "failure":
        delta["current_mode"] = "repair"
        delta["current_focus"] = "error_recovery"

    # 身份冲突 → 提升自我审查
    if perceived.get("identity_conflict", 0.0) > 0.5:
        delta["self_confidence_by_domain"] = {"self_monitoring": -0.1}

    return delta
