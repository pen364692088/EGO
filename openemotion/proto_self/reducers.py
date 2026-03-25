"""
Proto-Self Kernel v1 - Reducers

状态写回与策略推导。

设计约束：
- 所有更新必须是可序列化、可回放的
- policy_hint / response_tendency 只表达建议与倾向
- 不能包含直接工具执行命令
- 不能直接替 EgoCore 做现实裁决
"""

from typing import Any, Dict, Optional

from openemotion.proto_self.schemas import KernelEvent, ReflectionNote, ResponseTendency
from openemotion.proto_self.state import EpisodicRecord, ProtoSelfState


def update_identity_invariants(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    reflection_note: Optional[ReflectionNote],
) -> Dict[str, Any]:
    """
    更新 identity_invariants：只有高价值证据才能动。
    
    设计约束：
    - 不允许"一次事件改人格"
    - 只有身份冲突或高价值反思才能影响 identity
    """
    delta = {
        "core_roles_add": [],
        "core_commitments_add": [],
        "core_boundaries_add": [],
        "stable_preferences_patch": {},
        "identity_confidence_delta": 0.0,
    }

    if reflection_note and reflection_note.trigger == "identity_conflict":
        delta["identity_confidence_delta"] = -0.05

    return delta


def update_memory(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    cycle_delta: Dict[str, Any],
    reflection_note: Optional[ReflectionNote],
) -> Dict[str, Any]:
    """
    更新记忆：episodic_trace 写入 + cycle promotion hint。
    
    v1 不做大而全记忆系统，只做：
    - episodic_trace 写入
    - cycle 相关 promotion hint
    - reflection note promotion hint
    """
    return {
        "append_episode": True,
        "cycle_promotion_candidate": cycle_delta.get("cycle_id"),
        "promote_reflection": bool(reflection_note and reflection_note.promote_to_memory),
    }


def derive_policy_hint(
    state: ProtoSelfState,
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
    identity_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    推导策略提示：只产出倾向，不抢 EgoCore 裁决权。
    
    现有路线已经明确表达主权要由 EgoCore 程序端控制。
    """
    return {
        "risk_bias": "high" if appraisal_delta.get("caution", 0.0) > 0.7 else "normal",
        "closure_bias": appraisal_delta.get("completion_pressure", 0.0) > 0.6,
        "ask_preferred": appraisal_delta.get("caution", 0.0) > 0.8,
        "should_avoid_commitment_upgrade": True,
        "exploration_mode": self_model_delta.get("current_mode") == "exploration",
    }


def derive_response_tendency(
    state: ProtoSelfState,
    policy_hint: Dict[str, Any],
) -> Optional[ResponseTendency]:
    """
    推导响应倾向：影响下一步行为的内部偏置。
    """
    # 确定首选模式
    if policy_hint.get("ask_preferred"):
        preferred_mode = "ask"
    elif state.self_model.current_mode == "repair":
        preferred_mode = "repair"
    elif policy_hint.get("exploration_mode"):
        preferred_mode = "respond"
    else:
        preferred_mode = "respond"

    # 确定基调
    if policy_hint.get("risk_bias") == "high":
        preferred_tone = "cautious"
    else:
        preferred_tone = "calm"

    # 确定下一步建议
    if state.self_model.current_focus == "closure":
        suggested_next_step = "prioritize_closure"
    elif state.self_model.current_mode == "repair":
        suggested_next_step = "clarify_or_repair"
    elif policy_hint.get("exploration_mode"):
        suggested_next_step = "explore"
    else:
        suggested_next_step = "continue"

    return ResponseTendency(
        preferred_mode=preferred_mode,
        preferred_tone=preferred_tone,
        certainty_bound="bounded",
        suggested_next_step=suggested_next_step,
        ask_needed=policy_hint.get("ask_preferred", False),
    )


def apply_updates(
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
    
    设计约束：
    - 所有更新必须是确定性的
    - 必须可序列化
    - 必须可回放
    """
    from openemotion.proto_self.cycles import apply_cycle_delta

    # 1. 写 appraisal
    state.drives.coherence_pressure = appraisal_delta.get("coherence_pressure", state.drives.coherence_pressure)
    state.drives.curiosity = appraisal_delta.get("curiosity", state.drives.curiosity)
    state.drives.caution = appraisal_delta.get("caution", state.drives.caution)
    state.drives.completion_pressure = appraisal_delta.get("completion_pressure", state.drives.completion_pressure)
    state.drives.social_tension = appraisal_delta.get("social_tension", state.drives.social_tension)

    # 2. 写 self_model
    if self_model_delta.get("current_focus") is not None:
        state.self_model.current_focus = self_model_delta["current_focus"]
    if self_model_delta.get("current_mode") is not None:
        state.self_model.current_mode = self_model_delta["current_mode"]

    # 3. 写 cycle
    apply_cycle_delta(state.cycle_store, cycle_delta, event.timestamp)

    # 4. 写 episodic_trace
    if memory_update.get("append_episode"):
        state.episodic_trace.append(
            EpisodicRecord(
                event_id=event.event_id,
                perceived_summary=perceived,
                action_hint={},
                external_result=event.external_result,
                appraisal_snapshot=appraisal_delta,
            )
        )

    # 5. 写 identity（如果有变化）
    if identity_delta.get("identity_confidence_delta"):
        state.identity.identity_confidence += identity_delta["identity_confidence_delta"]
        state.identity.identity_confidence = max(0.0, min(1.0, state.identity.identity_confidence))

    # 6. revision counter
    if reflection_note:
        state.revision_counter += 1

    return state
