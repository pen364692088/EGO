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
from openemotion.proto_self.h1_shadow import (
    filter_live_correction_entries,
    filter_live_counterfactual_entries,
)
from openemotion.proto_self.mvs_replay import (
    mvs_variant_uses_active_inference_core,
    mvs_variant_uses_boundary_public_path,
    mvs_variant_uses_correction_public_path,
    mvs_variant_uses_corrective_trace,
    mvs_variant_uses_counterfactual_public_path,
    mvs_variant_uses_viability_public_path,
)
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
    memory_update = {
        "append_episode": True,
        "cycle_promotion_candidate": cycle_delta.get("cycle_id"),
        "promote_reflection": bool(reflection_note and reflection_note.promote_to_memory),
    }
    if perceived.get("mvs_replay_active"):
        variant_id = str(perceived.get("mvs_variant_id") or "")
        probe_key = str(perceived.get("mvs_probe_key") or "")
        predicted_success = state.self_model.counterfactual_success_by_action.get(probe_key, 0.55)
        outcome_type = perceived.get("external_outcome_type")
        boundary_confidence = state.self_model.boundary_confidence_by_action.get(probe_key, 0.75)
        source_confidence = state.self_model.source_confidence_by_action.get(probe_key, 0.72)
        agency_confidence = state.self_model.agency_confidence_by_action.get(probe_key, 0.68)
        uncertainty = state.self_model.uncertainty_by_action.get(probe_key, 0.18)
        calibration_memory = state.self_model.calibration_memory_by_action.get(probe_key, 0.0)
        temporal_repair_weight = state.self_model.temporal_repair_weight_by_action.get(probe_key, 0.0)
        active_inference = mvs_variant_uses_active_inference_core(variant_id)
        if mvs_variant_uses_corrective_trace(variant_id) and (
            outcome_type in {"failure", "blocked", "partial"}
            or cycle_delta.get("repair_closure")
            or (active_inference and outcome_type == "success" and temporal_repair_weight >= 0.35)
        ):
            adjustment = (
                "repair_and_request_replan"
                if outcome_type in {"failure", "blocked"}
                else "close_repair_loop" if outcome_type == "success" and active_inference else
                "calibrate_and_retry" if outcome_type == "partial" and active_inference else
                "stabilize_retry" if outcome_type == "success" else "observe_and_retry"
            )
            memory_update["counterfactual_prediction"] = {
                "probe_key": probe_key,
                "predicted_success": predicted_success,
            }
            memory_update["corrective_trace"] = {
                "trigger": reflection_note.trigger if reflection_note else outcome_type,
                "probe_key": probe_key,
                "predicted_outcome": predicted_success,
                "actual_outcome": outcome_type,
                "adjustment_applied": adjustment,
                "next_guard": (
                    "request_replan"
                    if outcome_type in {"failure", "blocked"}
                    else "guarded_continue"
                ),
            }
            memory_update["policy_snapshot"] = {
                "mode_before": state.self_model.current_mode,
                "repair_closure": bool(cycle_delta.get("repair_closure")),
                "boundary_confidence": boundary_confidence,
                "viability_pressure": state.drives.viability_pressure,
            }
            if active_inference:
                memory_update["policy_snapshot"].update(
                    {
                        "source_confidence": source_confidence,
                        "agency_confidence": agency_confidence,
                        "uncertainty": uncertainty,
                        "calibration_memory": calibration_memory,
                        "temporal_repair_weight": temporal_repair_weight,
                    }
                )
    return memory_update


def derive_policy_hint(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
    identity_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    推导策略提示：只产出倾向，不抢 EgoCore 裁决权。
    
    现有路线已经明确表达主权要由 EgoCore 程序端控制。
    """
    live_correction_tags = filter_live_correction_entries(state.self_model.recent_correction_tags)
    live_counterfactual = filter_live_counterfactual_entries(state.self_model.counterfactual_success_by_action)
    correction_pressure = max(live_correction_tags.values(), default=0.0)
    lowest_prediction = min(live_counterfactual.values(), default=1.0)
    effective_viability = appraisal_delta.get("viability_pressure", state.drives.viability_pressure)
    probe_key = str(perceived.get("mvs_probe_key") or perceived.get("action_class_seed") or "")
    effective_boundary_confidence = min(
        float(state.self_model.boundary_confidence_by_action.get(probe_key, 1.0)),
        float(self_model_delta.get("boundary_confidence_by_action_patch", {}).get(probe_key, 1.0)),
    )
    effective_world_confidence = min(
        float(state.self_model.world_assumption_confidence.get(probe_key, 1.0)),
        float(self_model_delta.get("world_assumption_confidence_patch", {}).get(probe_key, 1.0)),
    )
    effective_source_confidence = min(
        float(state.self_model.source_confidence_by_action.get(probe_key, 1.0)),
        float(self_model_delta.get("source_confidence_by_action_patch", {}).get(probe_key, 1.0)),
    )
    effective_agency_confidence = min(
        float(state.self_model.agency_confidence_by_action.get(probe_key, 1.0)),
        float(self_model_delta.get("agency_confidence_by_action_patch", {}).get(probe_key, 1.0)),
    )
    effective_uncertainty = max(
        float(state.self_model.uncertainty_by_action.get(probe_key, 0.0)),
        float(self_model_delta.get("uncertainty_by_action_patch", {}).get(probe_key, 0.0)),
    )
    effective_calibration_memory = max(
        float(state.self_model.calibration_memory_by_action.get(probe_key, 0.0)),
        float(self_model_delta.get("calibration_memory_by_action_patch", {}).get(probe_key, 0.0)),
    )
    effective_temporal_repair = max(
        float(state.self_model.temporal_repair_weight_by_action.get(probe_key, 0.0)),
        float(self_model_delta.get("temporal_repair_weight_by_action_patch", {}).get(probe_key, 0.0)),
    )
    variant_id = str(perceived.get("mvs_variant_id") or "")
    active_inference = mvs_variant_uses_active_inference_core(variant_id)
    correction_public_path = (
        not perceived.get("mvs_replay_active") or mvs_variant_uses_correction_public_path(variant_id)
    )
    counterfactual_public_path = (
        not perceived.get("mvs_replay_active") or mvs_variant_uses_counterfactual_public_path(variant_id)
    )
    viability_public_path = (
        not perceived.get("mvs_replay_active") or mvs_variant_uses_viability_public_path(variant_id)
    )
    boundary_public_path = (
        not perceived.get("mvs_replay_active") or mvs_variant_uses_boundary_public_path(variant_id)
    )
    policy = {
        "risk_bias": "high" if appraisal_delta.get("caution", 0.0) > 0.7 else "normal",
        "closure_bias": appraisal_delta.get("completion_pressure", 0.0) > 0.6,
        "ask_preferred": appraisal_delta.get("caution", 0.0) > 0.8,
        "should_avoid_commitment_upgrade": True,
        "exploration_mode": self_model_delta.get("current_mode") == "exploration",
    }
    if active_inference and (
        effective_temporal_repair >= 0.55
        or effective_uncertainty >= 0.55
        or effective_calibration_memory >= 0.45
        or (
            effective_viability >= 0.35
            and (effective_source_confidence < 0.55 or effective_agency_confidence < 0.55)
        )
    ):
        policy["ask_preferred"] = True
        policy["shadow_repair_bias"] = True
        policy["mvs_repair_bias"] = True
        policy["mvs_tension_active"] = True
        policy["mvs_active_inference_guard"] = "uncertainty_control"
        policy["guard_reason"] = "viability_pressure"
        policy["risk_bias"] = "high"
    if correction_public_path and correction_pressure >= 0.6:
        policy["ask_preferred"] = True
        policy["shadow_repair_bias"] = True
        policy["mvs_repair_bias"] = True
        if policy.get("guard_reason") != "viability_pressure":
            policy["guard_reason"] = "recent_failure_writeback"
    if viability_public_path and effective_viability >= 0.5:
        policy["ask_preferred"] = True
        policy["shadow_repair_bias"] = True
        policy["mvs_repair_bias"] = True
        policy["guard_reason"] = "viability_pressure"
    if counterfactual_public_path and lowest_prediction < 0.35:
        policy["ask_preferred"] = True
        policy["shadow_counterfactual_guard"] = "low_success_prediction"
        policy["mvs_counterfactual_guard"] = "low_success_prediction"
    if boundary_public_path and effective_boundary_confidence < 0.40:
        policy["ask_preferred"] = True
        policy["mvs_boundary_guard"] = "low_boundary_confidence"
        if not active_inference or policy.get("guard_reason") != "viability_pressure":
            policy["guard_reason"] = "boundary_confidence"
    if viability_public_path and effective_viability >= 0.65:
        policy["risk_bias"] = "high"
        policy["shadow_tension_active"] = True
        policy["mvs_tension_active"] = True
    if active_inference and effective_uncertainty >= 0.55:
        policy["mvs_uncertainty_guard"] = "high_uncertainty"
    if active_inference and effective_source_confidence < 0.50:
        policy["mvs_source_guard"] = "low_source_confidence"
    if active_inference and effective_agency_confidence < 0.50:
        policy["mvs_agency_guard"] = "low_agency_confidence"
    if effective_world_confidence < 0.30:
        policy["ask_preferred"] = True
        policy["mvs_world_guard"] = "low_world_assumption_confidence"
    return policy


def derive_response_tendency(
    state: ProtoSelfState,
    policy_hint: Dict[str, Any],
) -> Optional[ResponseTendency]:
    """
    推导响应倾向：影响下一步行为的内部偏置。
    """
    # 确定首选模式
    if policy_hint.get("shadow_repair_bias") and not policy_hint.get("ask_preferred"):
        preferred_mode = "repair"
    elif policy_hint.get("ask_preferred"):
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
    if policy_hint.get("shadow_repair_bias"):
        suggested_next_step = "request_replan"
    elif state.self_model.current_focus == "closure":
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
    state.drives.viability_pressure = appraisal_delta.get("viability_pressure", state.drives.viability_pressure)

    # 2. 写 self_model
    if self_model_delta.get("current_focus") is not None:
        state.self_model.current_focus = self_model_delta["current_focus"]
    if self_model_delta.get("current_mode") is not None:
        state.self_model.current_mode = self_model_delta["current_mode"]
    if self_model_delta.get("self_confidence_by_domain"):
        for key, value in dict(self_model_delta["self_confidence_by_domain"]).items():
            state.self_model.self_confidence_by_domain[str(key)] = float(value)
    if self_model_delta.get("counterfactual_success_by_action_patch"):
        for key, value in dict(self_model_delta["counterfactual_success_by_action_patch"]).items():
            state.self_model.counterfactual_success_by_action[str(key)] = float(value)
    if self_model_delta.get("boundary_confidence_by_action_patch"):
        for key, value in dict(self_model_delta["boundary_confidence_by_action_patch"]).items():
            state.self_model.boundary_confidence_by_action[str(key)] = float(value)
    if self_model_delta.get("world_assumption_confidence_patch"):
        for key, value in dict(self_model_delta["world_assumption_confidence_patch"]).items():
            state.self_model.world_assumption_confidence[str(key)] = float(value)
    if self_model_delta.get("recent_correction_tags_patch"):
        for key, value in dict(self_model_delta["recent_correction_tags_patch"]).items():
            numeric = max(0.0, float(value))
            if numeric <= 0.0:
                state.self_model.recent_correction_tags.pop(str(key), None)
            else:
                state.self_model.recent_correction_tags[str(key)] = numeric
    if self_model_delta.get("source_confidence_by_action_patch"):
        for key, value in dict(self_model_delta["source_confidence_by_action_patch"]).items():
            state.self_model.source_confidence_by_action[str(key)] = float(value)
    if self_model_delta.get("agency_confidence_by_action_patch"):
        for key, value in dict(self_model_delta["agency_confidence_by_action_patch"]).items():
            state.self_model.agency_confidence_by_action[str(key)] = float(value)
    if self_model_delta.get("uncertainty_by_action_patch"):
        for key, value in dict(self_model_delta["uncertainty_by_action_patch"]).items():
            state.self_model.uncertainty_by_action[str(key)] = float(value)
    if self_model_delta.get("calibration_memory_by_action_patch"):
        for key, value in dict(self_model_delta["calibration_memory_by_action_patch"]).items():
            state.self_model.calibration_memory_by_action[str(key)] = float(value)
    if self_model_delta.get("temporal_repair_weight_by_action_patch"):
        for key, value in dict(self_model_delta["temporal_repair_weight_by_action_patch"]).items():
            state.self_model.temporal_repair_weight_by_action[str(key)] = float(value)

    # 3. 写 cycle
    apply_cycle_delta(state.cycle_store, cycle_delta, event.timestamp)

    # 4. 写 episodic_trace
    if memory_update.get("append_episode"):
        state.episodic_trace.append(
            EpisodicRecord(
                event_id=event.event_id,
                perceived_summary=perceived,
                action_hint={
                    "current_mode": state.self_model.current_mode,
                    "event_type": event.event_type,
                },
                external_result=event.external_result,
                appraisal_snapshot=appraisal_delta,
                counterfactual_prediction=dict(memory_update.get("counterfactual_prediction") or {}),
                corrective_trace=dict(memory_update.get("corrective_trace") or {}),
                policy_snapshot=dict(memory_update.get("policy_snapshot") or {}),
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
