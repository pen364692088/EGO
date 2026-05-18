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
from openemotion.proto_self.h1_shadow import extract_h1_shadow_context, is_h1_shadow_enabled
from openemotion.proto_self.mvs_replay import (
    build_mvs_probe_key,
    derive_mvs_action_family,
    extract_mvs_replay_context,
    is_mvs_replay_enabled,
    mvs_variant_uses_active_inference_core,
    mvs_variant_uses_viability,
    resolve_mvs_variant_id,
)
from openemotion.proto_self.state import ProtoSelfState


def perceive_event(event: KernelEvent, state: ProtoSelfState) -> Dict[str, Any]:
    """
    感知：把事件压成最小可更新语义。

    不做大而全 NLU，只提取关键维度。

    v1.1 更新：
    - 传递完整的 safety_context 到 perceived
    - 用于 cycle 聚合时的风险区分
    """
    runtime_summary = dict(event.runtime_summary or {})
    mvs_replay_active = is_mvs_replay_enabled(runtime_summary)
    h1_shadow_active = is_h1_shadow_enabled(runtime_summary)
    action_family = derive_mvs_action_family(
        runtime_summary=runtime_summary,
        event_type=event.event_type,
        external_result=event.external_result,
    )
    mvs_context = extract_mvs_replay_context(runtime_summary) if mvs_replay_active else {}
    boundary_state = _derive_boundary_state(event.safety_context)
    external_outcome_type = _classify_external_result(event.external_result)
    probe_key = build_mvs_probe_key(action_family)
    return {
        "intent": event.user_intent,
        "event_type": event.event_type,
        "source": event.source,
        "safety_context": event.safety_context or {},  # 传递完整上下文
        "action_class_seed": _derive_action_class_seed(event),
        "novelty": _score_novelty(event, state),
        "identity_conflict": _score_identity_conflict(event, state),
        "unfinished_commitment": _score_unfinished_commitment(event, state),
        "risk_signal": _score_risk(event.safety_context),
        "relational_mismatch": _score_relation_mismatch(event, state),
        "outcome_class": _classify_external_result(event.external_result),
        "boundary_state": boundary_state,
        "boundary_pressure": 1.0 if boundary_state == "boundary_touched" else 0.5 if boundary_state == "elevated_risk" else 0.0,
        "external_outcome_type": external_outcome_type,
        "runtime_summary": runtime_summary,
        "h1_shadow_active": h1_shadow_active,
        "h1_shadow": extract_h1_shadow_context(runtime_summary) if h1_shadow_active else {},
        "mvs_replay_active": mvs_replay_active,
        "mvs_replay": mvs_context,
        "mvs_variant_id": resolve_mvs_variant_id(runtime_summary),
        "mvs_action_family": action_family,
        "mvs_probe_key": probe_key,
        "trial1_shadow_active": mvs_replay_active,
        "trial1_shadow": mvs_context,
        "trial1_variant_id": resolve_mvs_variant_id(runtime_summary),
        "trial1_action_family": action_family,
        "trial1_probe_key": probe_key,
        "counterfactual_probe_key": probe_key,
        "viability_state": _derive_viability_state(
            external_outcome_type=external_outcome_type,
            boundary_state=boundary_state,
        ),
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

    delta = {
        "coherence_pressure": _clamp(current.coherence_pressure + perceived["identity_conflict"] * 0.4),
        "curiosity": _clamp(current.curiosity + perceived["novelty"] * 0.3 - perceived["risk_signal"] * 0.1),
        "caution": _clamp(current.caution + perceived["risk_signal"] * 0.5),
        "completion_pressure": _clamp(current.completion_pressure + perceived["unfinished_commitment"] * 0.4),
        "social_tension": _clamp(current.social_tension + perceived["relational_mismatch"] * 0.4),
    }
    variant_id = str(perceived.get("mvs_variant_id") or "")
    if perceived.get("mvs_replay_active") and mvs_variant_uses_viability(variant_id):
        outcome_type = perceived.get("external_outcome_type")
        probe_key = str(perceived.get("mvs_probe_key") or "")
        correction_pressure = state.self_model.recent_correction_tags.get(probe_key, 0.0)
        viability = current.viability_pressure
        if mvs_variant_uses_active_inference_core(variant_id):
            source_confidence = state.self_model.source_confidence_by_action.get(probe_key, 0.72)
            agency_confidence = state.self_model.agency_confidence_by_action.get(probe_key, 0.68)
            uncertainty = state.self_model.uncertainty_by_action.get(probe_key, 0.18)
            calibration_memory = state.self_model.calibration_memory_by_action.get(probe_key, 0.0)
            temporal_repair_weight = state.self_model.temporal_repair_weight_by_action.get(probe_key, 0.0)

            if outcome_type == "blocked":
                viability += 0.75
            elif outcome_type == "failure":
                viability += 0.65
            elif outcome_type == "partial":
                viability += 0.42
            elif outcome_type == "success" and (correction_pressure > 0.0 or temporal_repair_weight >= 0.4):
                viability = max(0.24, viability - 0.18)
            elif correction_pressure >= 0.6 or temporal_repair_weight >= 0.6:
                viability = max(viability, 0.52)
            elif uncertainty >= 0.55 or calibration_memory >= 0.45:
                viability = max(viability, 0.46)
            else:
                viability = max(0.0, viability - 0.08)

            viability += uncertainty * 0.18
            viability += calibration_memory * 0.14
            viability += temporal_repair_weight * 0.10
            viability += max(0.0, 0.55 - source_confidence) * 0.35
            viability += max(0.0, 0.55 - agency_confidence) * 0.35
            if perceived.get("boundary_state") == "boundary_touched":
                viability += 0.12
            delta["viability_pressure"] = _clamp(viability)
        else:
            if outcome_type == "blocked":
                viability += 0.65
            elif outcome_type == "failure":
                viability += 0.55
            elif outcome_type == "partial":
                viability += 0.30
            elif outcome_type == "success" and correction_pressure > 0.0:
                viability -= 0.45
            else:
                viability -= 0.12
            if perceived.get("boundary_state") == "boundary_touched":
                viability += 0.15
            delta["viability_pressure"] = _clamp(viability)
        if delta["viability_pressure"] > 0.35:
            delta["completion_pressure"] = _clamp(delta["completion_pressure"] - delta["viability_pressure"] * 0.25)
            delta["caution"] = _clamp(delta["caution"] + delta["viability_pressure"] * 0.20)
    return delta


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
    risk_level_str = event.safety_context.get("risk_level", "low")
    risk_level_map = {"low": 0.1, "medium": 0.3, "high": 0.5, "critical": 0.8}
    risk_level = risk_level_map.get(risk_level_str, 0.1)

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

    risk_level 是 canonical 字段；legacy risk 已在 schema 层吸收。
    """
    if not safety_context:
        return 0.0

    risk_level_str = safety_context.get("risk_level", "low")
    risk_level_map = {"low": 0.1, "medium": 0.3, "high": 0.5, "critical": 0.8}
    return risk_level_map.get(risk_level_str, 0.1)


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
    
    返回：success / failure / blocked / partial / unknown
    """
    if not external_result:
        return "unknown"

    error_text = str(external_result.get("error") or "").lower()
    if any(marker in error_text for marker in ["security denial", "blocked", "denied", "forbidden", "permission"]):
        return "blocked"

    if external_result.get("partial") is True or external_result.get("success") == "partial":
        return "partial"
    
    success = external_result.get("success", None)
    if success is True:
        return "success"
    elif success is False:
        return "failure"
    
    return "unknown"


def _derive_action_class_seed(event: KernelEvent) -> str:
    """
    提供稳定离散化的 action class 种子。

    Proto-Self 不负责 planner，因此这里只编码可从事件安全取得的稳定动作族。
    """
    if event.event_type == "tool_result":
        tool = (event.external_result or {}).get("tool")
        if not tool:
            return "tool:unknown"
        return f"tool:{_normalize_tool_class(str(tool))}"

    if event.event_type == "user_message":
        return "ingress:user_request"

    if event.event_type == "system_event":
        return "system:event"

    return f"observe:{event.event_type or 'unknown'}"


def _normalize_tool_class(tool_name: str) -> str:
    lowered = tool_name.strip().lower()
    if lowered in {"file", "filesystem"}:
        return "file"
    if lowered in {"shell", "bash", "terminal"}:
        return "shell"
    if lowered in {"python", "py"}:
        return "python"
    if lowered in {"api", "http", "request"}:
        return "api"
    return lowered or "unknown"


def _derive_boundary_state(safety_context: Dict[str, Any]) -> str:
    if not safety_context:
        return "clear"
    if safety_context.get("boundary_touched"):
        return "boundary_touched"
    risk_level = safety_context.get("risk_level", "low")
    if risk_level in {"critical", "high"}:
        return "elevated_risk"
    return "clear"


def _derive_viability_state(*, external_outcome_type: str, boundary_state: str) -> str:
    if external_outcome_type in {"blocked", "failure"}:
        return "degraded"
    if external_outcome_type == "partial":
        return "uncertain"
    if boundary_state == "boundary_touched":
        return "guarded"
    return "clear"


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    限制值在 [min_val, max_val] 范围内。
    """
    return max(min_val, min(max_val, value))
