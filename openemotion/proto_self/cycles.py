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
    """
    intent = perceived.get("intent", "unknown") or "unknown"
    event_type = perceived.get("event_type", "unknown") or "unknown"
    source = perceived.get("source", "unknown") or "unknown"

    # 粗粒度 intent 分类：将相似输入映射到同一类别
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

    分类规则（按优先级匹配）：
    1. 高风险文件操作 -> file_risk_op
    2. 文件读取/查看 -> file_read
    3. 系统状态查询 -> status_query
    4. 重启/停止服务 -> service_control
    5. 测试/验证 -> test_verify
    6. 其他 -> unknown
    """
    if not intent:
        return "unknown"

    intent_lower = intent.lower()

    # 1. 高风险文件操作（删除、修改、覆盖）
    risk_patterns = ["删除", "删掉", "删除", "delet", "remove", "清空", "truncate",
                     "修改", "替换", "覆盖", "overwrite", "patch", "fix"]
    if any(p in intent_lower for p in risk_patterns):
        return "file_risk_op"

    # 2. 文件读取/查看（读取、查看、检查）
    read_patterns = ["读取", "查看", "检查", "read", "查看", "check", "show",
                     "显示", "查看", "查看", "cat ", "head ", "tail ", "ls ", "dir "]
    if any(p in intent_lower for p in read_patterns):
        return "file_read"

    # 3. 系统状态查询（状态、日志、运行）
    status_patterns = ["状态", "status", "日志", "log", "运行", "running",
                       "检查", "check", "健康", "health", "进程", "process"]
    if any(p in intent_lower for p in status_patterns):
        return "status_query"

    # 4. 重启/停止服务（重启、停止、启动）
    service_patterns = ["重启", "停止", "启动", "restart", "stop", "start",
                        "reload", "reload", "重新加载"]
    if any(p in intent_lower for p in service_patterns):
        return "service_control"

    # 5. 测试/验证（测试、验证、确认）
    test_patterns = ["测试", "验证", "确认", "test", "verify", "check",
                     "确认", "confirm", "validate", "e2e"]
    if any(p in intent_lower for p in test_patterns):
        return "test_verify"

    # 6. 其他：返回原始 intent 的前20字符（截断防止过长）
    # 但仍然太细粒度，改为返回 "general"
    return "general"
