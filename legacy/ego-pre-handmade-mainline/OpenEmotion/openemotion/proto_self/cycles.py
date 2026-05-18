"""
Proto-Self Kernel v1 - Cycle Consolidation

Cycle 固化：从事件—动作—后果反复出现中提炼可重入不变量。

设计约束：
- cycle 必须是稳定低熵、可重入、可写 trace、可 replay 的结构
- 只有反复出现、后果一致、与 identity 高相关的结构才能固化
- cycle 更新必须写 trace
- 不直接让 cycle 绕过 Governor
"""

import hashlib
from typing import Any, Dict

from openemotion.proto_self.schemas import KernelEvent
from openemotion.proto_self.mvs_replay import mvs_variant_uses_active_inference_core
from openemotion.proto_self.state import ProtoSelfState


def consolidate_cycles(
    state: ProtoSelfState,
    event: KernelEvent,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    固化 cycle：从反复出现的模式中提炼可重入不变量。
    
    当前升级目标：
    - cycle_id 不再只看 psi_bucket
    - closure signature 至少编码 event/action/outcome/mode
    - phi_signature 必须进入 promotion gating
    """
    psi_bucket = _build_psi_bucket(perceived)
    family_bucket = _build_family_bucket(perceived)
    action_signature = _build_action_signature(event, perceived)
    outcome_signature = _build_outcome_signature(perceived)
    mode_signature = _build_mode_signature(state, self_model_delta)
    phi_signature = _build_phi_signature(appraisal_delta, self_model_delta)
    closure_family_id = _stable_hash(f"{family_bucket}|{action_signature}")
    closure_signature = _stable_hash(
        f"{psi_bucket}|{action_signature}|{outcome_signature}|{mode_signature}"
    )
    closure_consistency_score = _compute_closure_consistency_score(
        state=state,
        closure_family_id=closure_family_id,
        outcome_signature=outcome_signature,
        phi_signature=phi_signature,
    )
    repair_closure = _is_repair_closure(
        state=state,
        action_signature=action_signature,
        outcome_signature=outcome_signature,
        mode_signature=mode_signature,
        perceived=perceived,
    )
    order_invariance_candidate = _build_order_invariance_candidate(
        state=state,
        psi_bucket=psi_bucket,
        action_signature=action_signature,
        outcome_signature=outcome_signature,
    )

    cycle_id = closure_signature
    existing = state.cycle_store.signatures.get(cycle_id)

    if existing:
        return {
            "cycle_id": cycle_id,
            "closure_signature": closure_signature,
            "closure_family_id": closure_family_id,
            "op": "strengthen",
            "psi_bucket": psi_bucket,
            "action_signature": action_signature,
            "outcome_signature": outcome_signature,
            "mode_signature": mode_signature,
            "phi_signature": phi_signature,
            "closure_consistency_score": closure_consistency_score,
            "repair_closure": repair_closure,
            "order_invariance_candidate": order_invariance_candidate,
            "strength_delta": 0.1,
        }

    return {
        "cycle_id": cycle_id,
        "closure_signature": closure_signature,
        "closure_family_id": closure_family_id,
        "op": "candidate",
        "psi_bucket": psi_bucket,
        "action_signature": action_signature,
        "outcome_signature": outcome_signature,
        "mode_signature": mode_signature,
        "phi_signature": phi_signature,
        "closure_consistency_score": closure_consistency_score,
        "repair_closure": repair_closure,
        "order_invariance_candidate": order_invariance_candidate,
        "strength_delta": 0.05,
    }


def apply_cycle_delta(
    cycle_store,
    cycle_delta: Dict[str, Any],
    timestamp: str,
) -> None:
    """
    应用 cycle delta 到 cycle_store。
    
    直接修改 cycle_store 对象。
    """
    from openemotion.proto_self.state import CycleSignature

    cycle_id = cycle_delta["cycle_id"]
    op = cycle_delta["op"]

    if op == "strengthen":
        existing = cycle_store.signatures.get(cycle_id)
        if existing:
            existing.strength = min(1.0, existing.strength + cycle_delta["strength_delta"])
            existing.hits += 1
            existing.last_seen_ts = timestamp
            existing.phi_signature = cycle_delta.get("phi_signature", existing.phi_signature)
            existing.mode_signature = cycle_delta.get("mode_signature", existing.mode_signature)
            existing.closure_consistency_score = cycle_delta.get(
                "closure_consistency_score",
                existing.closure_consistency_score,
            )

            if _should_promote(existing, cycle_delta):
                existing.promoted = True

    elif op == "candidate":
        cycle_store.signatures[cycle_id] = CycleSignature(
            cycle_id=cycle_id,
            closure_signature=cycle_delta["closure_signature"],
            closure_family_id=cycle_delta["closure_family_id"],
            psi_bucket=cycle_delta["psi_bucket"],
            action_signature=cycle_delta["action_signature"],
            outcome_signature=cycle_delta["outcome_signature"],
            mode_signature=cycle_delta["mode_signature"],
            phi_signature=cycle_delta["phi_signature"],
            strength=cycle_delta["strength_delta"],
            hits=1,
            last_seen_ts=timestamp,
            closure_consistency_score=cycle_delta.get("closure_consistency_score", 0.0),
            promoted=False,
        )


# ============================================================================
# Helper Functions
# ============================================================================

def _build_psi_bucket(perceived: Dict[str, Any]) -> str:
    """
    构建 psi_bucket：输入模式签名。

    使用粗粒度 intent 分类，让相似事件聚合到同一 cycle。
    例如：多次文件操作请求会命中同一 cycle，实现 strengthen。

    v1.1 更新：
    - 追加 safety_context.risk_level 到 psi_bucket
    - 高风险操作与低风险操作将被区分到不同 cycle
    - 向后兼容由 schema 层吸收，缺失时默认 "normal"
    """
    intent = perceived.get("intent", "unknown") or "unknown"
    event_type = perceived.get("event_type", "unknown") or "unknown"
    source = perceived.get("source", "unknown") or "unknown"

    # 粗粒度 intent 分类：将相似输入映射到同一类别
    coarse_intent = _coarse_intent_classify(intent)

    # 结构化上下文：风险等级
    # 高风险操作应与低风险操作区分
    safety_ctx = perceived.get("safety_context", {})
    risk_level = safety_ctx.get("risk_level", "normal") if safety_ctx else "normal"

    # 分层聚合策略：
    # - high/critical 风险：追加 risk 后缀，强制区分
    # - normal/low 风险：保持聚合，不追加后缀
    if risk_level in ["critical", "high"]:
        return f"{source}:{event_type}:{coarse_intent}:risk_{risk_level}"
    else:
        return f"{source}:{event_type}:{coarse_intent}"


def _build_family_bucket(perceived: Dict[str, Any]) -> str:
    """
    构建 family bucket：闭环族的粗粒度归一化键。

    family 只表达“这是哪一类 closure”，不能被风险后缀这种 outcome-adjacent
    信号拆开；细粒度差异继续留给 closure_signature 编码。
    """
    intent = perceived.get("intent", "unknown") or "unknown"
    event_type = perceived.get("event_type", "unknown") or "unknown"
    source = perceived.get("source", "unknown") or "unknown"
    coarse_intent = _coarse_intent_classify(intent)
    return f"{source}:{event_type}:{coarse_intent}"


def _build_phi_signature(
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
) -> str:
    """
    构建 phi_signature：内态变化签名。
    
    简化实现：基于 appraisal 和 self_model 的关键变化。
    """
    # 提取关键状态变化
    drive_changes = []
    for key in ["coherence_pressure", "caution", "curiosity"]:
        val = appraisal_delta.get(key, 0.0)
        if val > 0.1:
            drive_changes.append(f"{key}:+{val:.1f}")
        elif val < -0.1:
            drive_changes.append(f"{key}:{val:.1f}")

    mode_change = self_model_delta.get("current_mode")
    focus_change = self_model_delta.get("current_focus")

    parts = drive_changes
    if mode_change:
        parts.append(f"mode:{mode_change}")
    if focus_change:
        parts.append(f"focus:{focus_change}")

    return "|".join(parts) if parts else "neutral"


def _build_action_signature(event: KernelEvent, perceived: Dict[str, Any]) -> str:
    return perceived.get("action_class_seed", "unknown") or "unknown"


def _build_outcome_signature(perceived: Dict[str, Any]) -> str:
    outcome = perceived.get("outcome_class", "unknown") or "unknown"
    if outcome in {"success", "failure", "blocked", "partial"}:
        return outcome
    return "unknown"


def _build_mode_signature(state: ProtoSelfState, self_model_delta: Dict[str, Any]) -> str:
    return self_model_delta.get("current_mode") or state.self_model.current_mode or "baseline"


def _compute_closure_consistency_score(
    *,
    state: ProtoSelfState,
    closure_family_id: str,
    outcome_signature: str,
    phi_signature: str,
) -> float:
    family_members = [
        signature
        for signature in state.cycle_store.signatures.values()
        if signature.closure_family_id == closure_family_id
    ]

    if outcome_signature == "unknown":
        return 0.35

    if not family_members:
        return 0.75

    family_hits = sum(member.hits for member in family_members)
    same_outcome_hits = sum(
        member.hits for member in family_members if member.outcome_signature == outcome_signature
    )
    same_phi_hits = sum(
        member.hits for member in family_members if member.phi_signature == phi_signature
    )

    outcome_ratio = same_outcome_hits / family_hits if family_hits else 0.0
    phi_ratio = same_phi_hits / family_hits if family_hits else 0.0
    return round(min(1.0, 0.6 * outcome_ratio + 0.4 * phi_ratio), 3)


def _is_repair_closure(
    *,
    state: ProtoSelfState,
    action_signature: str,
    outcome_signature: str,
    mode_signature: str,
    perceived: Dict[str, Any],
) -> bool:
    if outcome_signature != "success":
        return False
    return _has_recent_repair_precursor(
        state=state,
        action_signature=action_signature,
        allow_partial=mvs_variant_uses_active_inference_core(str(perceived.get("mvs_variant_id") or "")),
    )


def _has_recent_repair_precursor(*, state: ProtoSelfState, action_signature: str, allow_partial: bool) -> bool:
    action_family = action_signature.split(":", 1)[-1]
    for record in reversed(state.episodic_trace):
        perceived_summary = record.perceived_summary or {}
        if perceived_summary.get("event_type") != "tool_result":
            continue

        previous_action = _extract_record_action_signature(record)
        if not previous_action:
            continue

        previous_family = previous_action.split(":", 1)[-1]
        if previous_action != action_signature and previous_family != action_family:
            continue

        previous_outcome = _extract_record_outcome_signature(record)
        if previous_outcome in {"failure", "blocked"}:
            return True
        if allow_partial and previous_outcome == "partial":
            return True
        if previous_outcome == "success":
            return False
    return False


def _extract_record_action_signature(record) -> str:
    perceived_summary = record.perceived_summary or {}
    action_signature = perceived_summary.get("action_class_seed")
    if action_signature:
        return str(action_signature)

    result = record.external_result or {}
    tool = str(result.get("tool") or "").strip().lower()
    if not tool:
        return ""
    return f"tool:{tool}"


def _extract_record_outcome_signature(record) -> str:
    perceived_summary = record.perceived_summary or {}
    outcome = perceived_summary.get("external_outcome_type") or perceived_summary.get("outcome_class")
    if outcome in {"success", "failure", "blocked", "partial"}:
        return str(outcome)

    result = record.external_result or {}
    if result.get("success") is True:
        return "success"
    if result.get("success") is False:
        return "failure"
    return "unknown"


def _build_order_invariance_candidate(
    *,
    state: ProtoSelfState,
    psi_bucket: str,
    action_signature: str,
    outcome_signature: str,
) -> str:
    precursor_buckets = []
    for record in reversed(state.episodic_trace):
        perceived_summary = record.perceived_summary or {}
        if perceived_summary.get("event_type") == "tool_result":
            continue
        precursor_buckets.append(_build_psi_bucket(perceived_summary))
        if len(precursor_buckets) >= 3:
            break

    precursor_buckets.sort()
    payload = "|".join(precursor_buckets + [psi_bucket, action_signature, outcome_signature])
    return _stable_hash(payload)


def _should_promote(signature, cycle_delta: Dict[str, Any]) -> bool:
    if signature.strength <= 0.5 or signature.hits <= 3:
        return False

    consistency = cycle_delta.get("closure_consistency_score", signature.closure_consistency_score)
    repair_closure = bool(cycle_delta.get("repair_closure"))
    outcome_known = signature.outcome_signature != "unknown"

    return (outcome_known and consistency >= 0.75) or repair_closure


def _stable_hash(s: str) -> str:
    """
    生成稳定哈希值。

    使用 SHA256 的前 16 字符作为 cycle_id。
    """
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _coarse_intent_classify(intent: str) -> str:
    """
    粗粒度 intent 分类：将相似输入映射到同一类别。

    这样相似事件（如多次文件操作）会命中同一 cycle，实现 strengthen。

    v1.1 更新：
    - 修复关键词优先级冲突
    - 优化中文关键词覆盖
    - 使用更精确的匹配规则

    分类规则（按优先级匹配，高优先级先匹配）：
    1. 高风险文件操作 -> file_risk_op（删除、修改、覆盖）
    2. 服务控制 -> service_control（重启、停止、启动）- 提前避免被"运行"等词误匹配
    3. 测试/验证 -> test_verify（测试、验证、e2e）
    4. 系统状态查询 -> status_query（状态、日志、健康）- "检查健康"优先于此
    5. 文件读取/查看 -> file_read（读取、查看、显示）
    6. 其他 -> general
    """
    if not intent:
        return "unknown"

    intent_lower = intent.lower()

    # 1. 高风险文件操作（删除、修改、覆盖）- 最高优先级
    risk_patterns = ["删除", "删掉", "delet", "remove", "清空", "truncate",
                     "修改", "替换", "覆盖", "overwrite", "patch"]
    if any(p in intent_lower for p in risk_patterns):
        return "file_risk_op"

    # 2. 服务控制（重启、停止、启动）- 提前避免被"运行"等词误匹配
    service_patterns = ["重启", "停止", "启动", "restart", "stop", "start",
                        "reload", "重新加载"]
    if any(p in intent_lower for p in service_patterns):
        return "service_control"

    # 3. 测试/验证（测试、验证、e2e）- 提前避免被"运行测试"中的"运行"误匹配
    test_patterns = ["测试", "验证", "确认", "test", "verify",
                     "confirm", "validate", "e2e"]
    if any(p in intent_lower for p in test_patterns):
        return "test_verify"

    # 4. 系统状态查询（状态、日志、健康）
    # 注意："检查代码"不会被匹配，因为不包含这些关键词
    status_patterns = ["状态", "status", "日志", "log", "running",
                       "健康", "health", "进程", "process"]
    if any(p in intent_lower for p in status_patterns):
        return "status_query"

    # 5. 文件读取/查看（读取、查看、显示）
    # 注意：放在 status_query 之后，让"检查健康状态"优先匹配 status_query
    # "check file/content" 视为文件读取，但单独的 "check" 不算
    read_patterns = ["读取", "查看", "read", "show", "显示",
                     "cat ", "head ", "tail ", "ls ", "dir ",
                     "check file", "check content"]  # check + 文件相关词
    if any(p in intent_lower for p in read_patterns):
        return "file_read"

    # 6. 其他
    return "general"
