# P1-A Stability Review

> 审查日期: 2026-03-16
> 审查对象: P1-A Identity Invariants v1
> 审查结论: **STABLE**

---

## 1. 审查范围

| 文件 | 行数 | 用途 |
|------|------|------|
| contracts/identity_invariants.schema.json | 330 | Schema 定义 |
| docs/IDENTITY_INVARIANTS_CONTRACT.md | 200 | 契约文档 |
| egocore/runtime/identity_guard.py | 400 | 守卫实现 |
| tests/test_identity_guard.py | 270 | 测试覆盖 |

---

## 2. 必查项结果

### 2.1 是否只包含长期身份边界字段

**结果: ✅ PASS**

Schema 中的字段分类：

| 字段 | 类型 | 说明 |
|------|------|------|
| identity_handle | 不可变 | 系统唯一标识 |
| core_name | 可变(受限) | 显示名称 |
| core_role | 不可变 | 核心角色定位 |
| owner_relationship | 不可变 | 所有权关系 |
| system_scope | 可变(受限) | 系统范围 |
| non_negotiable_commitments | 可变(受限) | 核心承诺 |
| forbidden_self_rewrite_zones | 不可变 | 禁止改写区域 |
| safety_boundaries | 可变(受限) | 安全边界 |
| tool_authority_boundary | 可变(受限) | 工具权限边界 |
| allowed_change_rules | 元数据 | 变更规则定义 |
| temporary_state | 可变 | 临时状态 |

**结论**: 所有字段都是身份边界相关，无运行时状态混入。

### 2.2 是否混入 self-model 语义

**结果: ✅ PASS - 未混入**

Self-model 典型字段检查：

| Self-model 字段 | 是否存在于 invariants | 结论 |
|----------------|----------------------|------|
| capabilities | ❌ 不存在 | PASS |
| limitations | ❌ 不存在 | PASS |
| active_goals | ❌ 不存在 | PASS |
| current_mode | ❌ 不存在 | PASS |
| confidence_by_domain | ❌ 不存在 | PASS |
| current_internal_state_summary | ❌ 不存在 | PASS |

**临时状态字段审查**：

| temporary_state 字段 | 是否越界 | 分析 |
|---------------------|---------|------|
| active_focus | ❌ 不越界 | 明确标注"不属于长期身份" |
| short_term_mode | ❌ 不越界 | 明确标注"不属于长期身份" |
| temporary_task_posture | ❌ 不越界 | 明确标注"不属于长期身份" |
| recent_learned_constraints | ❌ 不越界 | 明确标注"不属于长期身份" |

**结论**: temporary_state 字段已明确标注为临时状态，边界清晰。

### 2.3 是否允许普通外部事件改写核心身份

**结果: ✅ PASS - 不允许**

identity_guard.py 中的保护机制：

```python
def validate_external_event(self, event: Dict[str, Any]) -> bool:
    identity_changes = event.get("metadata", {}).get("identity_changes", [])
    for change in identity_changes:
        field_path = change.get("field_path")
        if field_path in self.ABSOLUTELY_IMMUTABLE:
            raise ImmutableFieldError(...)
```

测试验证：
- `test_external_event_blocked_for_immutable`: ✅ PASS

**结论**: 外部事件无法改写核心身份。

### 2.4 identity_guard 是否只做守卫与校验

**结果: ✅ PASS - 只做守卫**

职责分析：

| 职责 | 是否实现 | 是否越界 |
|------|---------|---------|
| 加载身份不变量 | ✅ | 否 |
| 验证变更请求 | ✅ | 否 |
| 拦截非法改写 | ✅ | 否 |
| 记录审计轨迹 | ✅ | 否 |
| 能力推断 | ❌ | N/A |
| 目标管理 | ❌ | N/A |
| 策略生成 | ❌ | N/A |
| 情感/评价逻辑 | ❌ | N/A |
| 自我模型逻辑 | ❌ | N/A |

**结论**: identity_guard 职责纯粹，无越界逻辑。

### 2.5 审计记录是否完整

**结果: ✅ PASS**

审计记录内容：
- ✅ timestamp
- ✅ field_path
- ✅ old_value
- ✅ new_value
- ✅ trigger
- ✅ authorized
- ✅ approver (可选)

失败时显式报错：
- ✅ ImmutableFieldError
- ✅ UnauthorizedChangeError
- ✅ ValidationFailedError

---

## 3. 测试覆盖审查

| 测试类 | 测试数 | 覆盖内容 |
|-------|-------|---------|
| TestIdentityGuardLoading | 3 | 加载验证 |
| TestImmutableFieldProtection | 3 | 不可变保护 |
| TestMutableFieldChanges | 3 | 可变变更 |
| TestApprovalRequiredChanges | 2 | 审批流程 |
| TestAuditTrail | 2 | 审计轨迹 |
| TestExternalEventValidation | 2 | 外部事件拦截 |
| TestRejectChange | 1 | 拒绝记录 |

**总计**: 16 tests, 全部通过

---

## 4. 稳定性评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 职责边界清晰度 | 10/10 | 完全符合 P1-A 定义 |
| Self-model 隔离 | 10/10 | 无混入 |
| 外部事件防护 | 10/10 | 完整拦截 |
| 审计完整性 | 10/10 | 所有关键字段记录 |
| 测试覆盖 | 10/10 | 16 tests 全通过 |
| **总评** | **10/10** | **STABLE** |

---

## 5. 结论

**P1-A Identity Invariants v1 状态: STABLE**

- ✅ 只包含长期身份边界字段
- ✅ 未混入 self-model 语义
- ✅ 外部事件无法改写核心身份
- ✅ identity_guard 只做守卫与校验
- ✅ 审计记录完整
- ✅ 测试覆盖充分

**建议**: 可以进入 P1-B。
