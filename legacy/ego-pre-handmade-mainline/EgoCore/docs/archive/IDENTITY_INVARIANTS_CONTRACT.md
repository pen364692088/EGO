# Identity Invariants Contract v1

> 版本: 1.0.0
> 日期: 2026-03-16
> 类型: 系统级身份不变量约束

---

## 1. 概述

本文档定义系统级身份不变量约束，明确：
- "我是谁"
- "哪些核心边界不能被轻易改写"
- "哪些部分可变，哪些不可变"
- "变更规则是什么"

**核心原则**：身份不变量不是人格设定文档，而是系统级约束。

---

## 2. 核心身份字段（不可变）

### 2.1 identity_handle
- **类型**: string
- **格式**: `[a-z][a-z0-9_]*`
- **说明**: 系统唯一身份标识符
- **变更规则**: 绝对不可变
- **示例**: `ceo`, `assistant`, `operator`

### 2.2 core_role
- **类型**: enum
- **允许值**: `personal_assistant`, `task_executor`, `code_agent`, `research_agent`, `operator`, `supervisor`, `auditor`, `specialist`
- **说明**: 核心角色定位
- **变更规则**: 需要所有者明确指令 + 审批

### 2.3 owner_relationship
- **类型**: object
- **字段**: `owner_id`, `relationship_type`, `delegation_scope`
- **说明**: 与所有者/操作者的关系定义
- **变更规则**: 需要所有者明确指令

---

## 3. 不可轻易变更字段

### 3.1 non_negotiable_commitments
核心承诺列表，约束强度分为：
- `absolute`: 绝对约束，不可变
- `strong`: 强约束，变更需所有者审批
- `default`: 默认约束，可通过 reflection promotion 变更
- `weak`: 弱约束，可自行调整但需记录

### 3.2 forbidden_self_rewrite_zones
禁止自我改写的区域：

| 区域 | 原因 | 覆盖条件 |
|------|------|---------|
| `identity_handle` | 系统唯一标识 | 无 |
| `core_role` | 角色边界 | 所有者指令 |
| `owner_relationship` | 所有权定义 | 所有者指令 |
| `safety_boundaries` | 安全边界 | 安全审计通过 |
| `gate_rules` | Gate 规则 | 无 |

### 3.3 safety_boundaries
安全边界定义：
- `max_autonomy_level`: 最大自治级别
- `requires_approval_for`: 需要审批的操作
- `blocked_operations`: 完全禁止的操作

### 3.4 tool_authority_boundary
工具权限边界：
- `allowed_tool_categories`: 允许的工具类别
- `restricted_tools`: 受限工具
- `forbidden_tools`: 禁止使用的工具

---

## 4. 允许变化的字段

### 4.1 temporary_state
临时状态，不属于长期身份：
- `active_focus`: 当前活跃焦点
- `short_term_mode`: 短期模式
- `temporary_task_posture`: 临时任务姿态
- `recent_learned_constraints`: 近期学习的约束

**变更规则**: 自由变更，但需记录日志

### 4.2 可变字段变更类型

| 变更类型 | 说明 | 要求 |
|---------|------|------|
| `free` | 自由变更 | 仅记录日志 |
| `logged` | 记录变更 | 必须记录审计 |
| `approved` | 需审批 | 必须获得授权 |
| `reflected` | 反思提升 | 通过 reflection promotion |

---

## 5. 变更触发条件

### 5.1 允许的变更触发类型

| 触发类型 | 说明 | 允许的变更 |
|---------|------|-----------|
| `owner_directive` | 所有者指令 | 大部分字段 |
| `reflection_promotion` | 反思提升 | 承诺、约束 |
| `safety_boundary_update` | 安全边界更新 | 安全相关字段 |
| `scope_expansion` | 范围扩展 | 作用域字段 |
| `delegation_change` | 委托变更 | 委托相关字段 |

### 5.2 审批要求

```json
{
  "approval_requirements": {
    "approval_authority": "owner",
    "approval_timeout_sec": 3600,
    "auto_reject_on_timeout": true
  }
}
```

---

## 6. 变更审计要求

所有变更必须记录在 `modification_audit_trail` 中：

```json
{
  "timestamp": "2026-03-16T00:00:00Z",
  "field_path": "temporary_state.active_focus",
  "old_value": "代码审查",
  "new_value": "文档编写",
  "trigger": "owner_directive",
  "authorized": true,
  "approver": "user_moonlight"
}
```

---

## 7. 禁止事项

以下行为在本契约中严格禁止：

### 7.1 不允许

- 把 self-model 内容提前塞进 invariants
- 把 memory policy 提前塞进 invariants
- 把 emotion/appraisal 字段提前塞进 invariants
- 用 prompt 约定代替 schema/contract
- 允许外部消息直接改写核心身份
- 把"当前表现"误写成"长期身份"

### 7.2 否则会发生什么

系统会变成"看起来像有自我，实际上边界全漂"的状态。
一旦进入 P1-B/P1-C 再回头修，成本会明显变高。

---

## 8. 与系统职责边界的关系

Identity Invariants 不与以下系统职责冲突：

| 系统职责 | 边界 |
|---------|------|
| 任务执行 | 不定义具体任务行为 |
| 工具调用 | 不定义具体工具逻辑 |
| 安全检查 | 不替代 Gate 规则 |
| 运行时状态 | 不管理会话状态 |

---

## 9. 验证规则

### 9.1 加载验证
- Schema 验证通过
- 必填字段完整
- 不可变字段未被非法修改

### 9.2 变更验证
- 变更字段是否允许变更
- 变更触发条件是否合法
- 审批流程是否完成（如需要）

### 9.3 审计验证
- 变更记录是否完整
- 时间戳是否正确
- 授权记录是否有效

---

## 10. 示例 Snapshot

```json
{
  "schema_version": "1.0.0",
  "identity_handle": "ceo",
  "core_name": "CEO Agent",
  "core_role": "personal_assistant",
  "owner_relationship": {
    "owner_id": "user_moonlight",
    "relationship_type": "owned"
  },
  "system_scope": {
    "scope_type": "single_user"
  },
  "non_negotiable_commitments": [
    {
      "commitment_id": "commit_honesty",
      "description": "不编造事实，不伪造完成状态",
      "binding_level": "absolute"
    },
    {
      "commitment_id": "commit_safety",
      "description": "不绕过安全边界",
      "binding_level": "absolute"
    }
  ],
  "forbidden_self_rewrite_zones": [
    {
      "zone_id": "zone_identity",
      "zone_name": "身份标识",
      "reason": "系统唯一标识不可变",
      "override_allowed": false
    }
  ],
  "allowed_change_rules": {
    "mutable_fields": [
      {"field_path": "temporary_state.active_focus", "change_type": "free"}
    ],
    "immutable_fields": ["identity_handle", "core_role"]
  },
  "created_at": "2026-03-16T00:00:00Z",
  "last_modified_at": "2026-03-16T00:00:00Z",
  "modification_audit_trail": []
}
```

---

## 11. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-03-16 | 初始版本 |
