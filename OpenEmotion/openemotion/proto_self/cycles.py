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

from openemotion.proto_self.state import ProtoSelfState


def consolidate_cycles(
    state: ProtoSelfState,
    perceived: Dict[str, Any],
    appraisal_delta: Dict[str, Any],
    self_model_delta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    固化 cycle：从反复出现的模式中提炼可重入不变量。
    
    返回：
    - cycle_id: cycle 唯一标识（只基于 psi_bucket）
    - op: strengthen / candidate
    - psi_bucket: 输入模式签名
    - phi_signature: 内态变化签名
    - strength_delta: 强度变化
    """
    psi_bucket = _build_psi_bucket(perceived)
    phi_signature = _build_phi_signature(appraisal_delta, self_model_delta)

    # cycle_id 只基于 psi_bucket（稳定的输入模式）
    cycle_id = _stable_hash(psi_bucket)
    existing = state.cycle_store.signatures.get(cycle_id)

    if existing:
        # 已存在 → 强化
        return {
            "cycle_id": cycle_id,
            "op": "strengthen",
            "psi_bucket": psi_bucket,
            "phi_signature": phi_signature,
            "strength_delta": 0.1,
        }

    # 新 candidate
    return {
        "cycle_id": cycle_id,
        "op": "candidate",
        "psi_bucket": psi_bucket,
        "phi_signature": phi_signature,
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
        # 强化现有 cycle
        existing = cycle_store.signatures.get(cycle_id)
        if existing:
            existing.strength = min(1.0, existing.strength + cycle_delta["strength_delta"])
            existing.hits += 1
            existing.last_seen_ts = timestamp

            # 晋升门槛：strength > 0.5 且 hits > 3
            if existing.strength > 0.5 and existing.hits > 3:
                existing.promoted = True

    elif op == "candidate":
        # 创建新 candidate
        cycle_store.signatures[cycle_id] = CycleSignature(
            cycle_id=cycle_id,
            psi_bucket=cycle_delta["psi_bucket"],
            phi_signature=cycle_delta["phi_signature"],
            strength=cycle_delta["strength_delta"],
            hits=1,
            last_seen_ts=timestamp,
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
