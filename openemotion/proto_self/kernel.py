"""
Proto-Self Kernel v1 - Main Kernel

统一递归更新器：把事件、当前自我状态、历史轨迹、外部后果重新折叠成"下一状态 + 下一步倾向"。

设计约束：
- 只做统一递归更新器
- 不做模块膨胀
- 不做人格大杂烩
- failure 必须可回流
- cycle 必须可固化、可 trace、可 replay
"""

from typing import Any, Dict, Optional
from datetime import datetime

from openemotion.proto_self.schemas import (
    KernelEvent,
    KernelOutput,
    ReflectionNote,
    ResponseTendency,
    SCHEMA_VERSION,
)
from openemotion.proto_self.state import ProtoSelfState
from openemotion.proto_self.trace_types import build_trace_payload


def process_event(state: ProtoSelfState, event: KernelEvent) -> KernelOutput:
    """
    Proto-Self Kernel 主循环。
    
    输入：当前状态 + 结构化事件
    输出：状态增量 + 策略倾向 + trace payload
    
    设计意图：
    - 事件进入 → 内态更新 → 倾向生成 → 后果回流 → 强化/削弱自我不变量
    """
    # 1. 感知：把事件压成最小可更新语义
    perceived = _perceive(event, state)

    # 2. Appraisal：更新 drive_field
    appraisal_delta = _update_drive_field(state, perceived)

    # 3. Self-Model 更新
    self_model_delta = _update_self_model(state, perceived, appraisal_delta)

    # 4. Cycle 固化
    cycle_delta = _consolidate_cycles(state, perceived, appraisal_delta, self_model_delta)

    # 5. 反思（如有必要）
    reflection_note = _maybe_reflect(state, event, perceived, appraisal_delta, self_model_delta)

    # 6. Identity 更新（只有高价值证据才能动）
    identity_delta = _update_identity_invariants(state, perceived, reflection_note)

    # 7. 记忆更新
    memory_update = _update_memory(state, perceived, cycle_delta, reflection_note)

    # 8. 策略推导
    policy_hint = _derive_policy_hint(state, appraisal_delta, self_model_delta, identity_delta)

    # 9. 响应倾向
    response_tendency = _derive_response_tendency(state, policy_hint)

    # 10. 状态写回
    next_state = _apply_updates(
        state=state,
        event=event,
        perceived=perceived,
        appraisal_delta=appraisal_delta,
        self_model_delta=self_model_delta,
        cycle_delta=cycle_delta,
        identity_delta=identity_delta,
        memory_update=memory_update,
        reflection_note=reflection_note,
    )

    # 11. 构建 trace payload
    trace_payload = build_trace_payload(
        event_id=event.event_id,
        perceived=perceived,
        appraisal_delta=appraisal_delta,
        self_model_delta=self_model_delta,
        cycle_delta=cycle_delta,
        identity_delta=identity_delta,
        reflection_trigger=reflection_note.trigger if reflection_note else None,
        policy_hint=policy_hint,
        timestamp=event.timestamp,
    )

    # 12. 构建输出
    return KernelOutput(
        schema_version=SCHEMA_VERSION,
        event_id=event.event_id,
        identity_state_delta=identity_delta,
        self_model_delta=self_model_delta,
        memory_update=memory_update,
        appraisal_state_delta=appraisal_delta,
        reflection_note=reflection_note,
        policy_hint=policy_hint,
        response_tendency=response_tendency,
        confidence_meta=_compute_confidence_meta(next_state),
        trace_payload=trace_payload,
    )


# ============================================================================
# Helper Functions (to be implemented in separate modules)
# ============================================================================

def _perceive(event: KernelEvent, state: ProtoSelfState) -> Dict[str, Any]:
    """
    感知：把事件压成最小可更新语义。
    
    不做大而全 NLU，只提取关键维度。
    """
    from openemotion.proto_self.appraisal import perceive_event
    return perceive_event(event, state)


def _update_drive_field(state: ProtoSelfState, perceived: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新 drive_field：功能性偏置，不是情绪文案。
    """
    from openemotion.proto_self.appraisal import update_drive_field
    return update_drive_field(state, perceived)


def _update_self_model(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    更新 self_model：最小可测更新。
    """
    from openemotion.proto_self.self_model import update_self_model
    return update_self_model(state, perceived, appraisal_delta)


def _consolidate_cycles(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Cycle 固化：从反复出现中提炼可重入不变量。
    """
    from openemotion.proto_self.cycles import consolidate_cycles
    return consolidate_cycles(state, perceived, appraisal_delta, self_model_delta)


def _maybe_reflect(
    state: ProtoSelfState,
    event: KernelEvent,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
) -> Optional[ReflectionNote]:
    """
    反思：只在必要时触发，不能把 reflection 做成第二个大脑。
    """
    from openemotion.proto_self.reflection import maybe_reflect
    return maybe_reflect(state, event, perceived, appraisal_delta, self_model_delta)


def _update_identity_invariants(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    reflection_note: Optional[ReflectionNote],
) -> Dict[str, Any]:
    """
    更新 identity_invariants：只有高价值证据才能动。
    """
    from openemotion.proto_self.reducers import update_identity_invariants
    return update_identity_invariants(state, perceived, reflection_note)


def _update_memory(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    cycle_delta: Dict[str, Any],
    reflection_note: Optional[ReflectionNote],
) -> Dict[str, Any]:
    """
    更新记忆：episodic_trace 写入 + cycle promotion hint。
    """
    from openemotion.proto_self.reducers import update_memory
    return update_memory(state, perceived, cycle_delta, reflection_note)


def _derive_policy_hint(
    state: ProtoSelfState,
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
    identity_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    推导策略提示：只产出倾向，不抢 EgoCore 裁决权。
    """
    from openemotion.proto_self.reducers import derive_policy_hint
    return derive_policy_hint(state, appraisal_delta, self_model_delta, identity_delta)


def _derive_response_tendency(
    state: ProtoSelfState,
    policy_hint: Dict[str, Any],
) -> Optional[ResponseTendency]:
    """
    推导响应倾向：影响下一步行为的内部偏置。
    """
    from openemotion.proto_self.reducers import derive_response_tendency
    return derive_response_tendency(state, policy_hint)


def _apply_updates(
    state: ProtoSelfState,
    event: KernelEvent,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
    cycle_delta: Dict[str, Any],
    identity_delta: Dict[str, Any],
    memory_update: Dict[str, Any],
    reflection_note: Optional[ReflectionNote],
) -> ProtoSelfState:
    """
    状态写回：把所有增量应用到状态。
    """
    from openemotion.proto_self.reducers import apply_updates
    return apply_updates(
        state=state,
        event=event,
        perceived=perceived,
        appraisal_delta=appraisal_delta,
        self_model_delta=self_model_delta,
        cycle_delta=cycle_delta,
        identity_delta=identity_delta,
        memory_update=memory_update,
        reflection_note=reflection_note,
    )


def _compute_confidence_meta(state: ProtoSelfState) -> Dict[str, Any]:
    """
    计算置信度元数据。
    """
    return {
        "identity_confidence": state.identity.identity_confidence,
        "revision_count": state.revision_counter,
        "cycle_count": len(state.cycle_store.signatures),
        "episodic_count": len(state.episodic_trace),
    }
