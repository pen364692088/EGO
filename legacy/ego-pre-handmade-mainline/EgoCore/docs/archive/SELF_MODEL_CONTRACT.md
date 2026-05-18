# Self-Model Contract v1

> 版本: 1.0.0
> 日期: 2026-03-16
> 类型: 结构化自我模型

---

## 1. 概述

Self-Model 定义系统对自己的能力、限制、目标与当前状态的**结构化认知**。

**核心原则**：
- Self-Model 是结构化状态，不是叙述文本
- Self-Model 是自我认知的"能力清单"，不是人格设定
- Self-Model 可以变化，但变更必须可追踪、可审计

---

## 2. 与 Identity Invariants 的关系

| 维度 | Identity Invariants | Self-Model |
|------|---------------------|------------|
| 定义 | "我是谁" | "我能做什么" |
| 变更频率 | 低 | 中 |
| 变更规则 | 严格限制 | 按规则更新 |
| 典型字段 | identity_handle, core_role | capabilities, limitations |

**关键约束**：
- Self-Model 不能修改 Identity Invariants
- Self-Model 的 standing_commitments 引用 Identity Invariants
- Self-Model 的 tool_authority_boundary 与 Identity Invariants 对齐

---

## 3. 核心字段定义

### 3.1 capabilities（能力）

描述当前具备的能力。

```json
{
  "capability_id": "cap_file_read",
  "name": "文件读取",
  "category": "file_operations",
  "current_level": "advanced",
  "constraints": ["仅限用户授权目录"],
  "last_verified_at": "2026-03-16T00:00:00Z"
}
```

**能力类别**：
- `file_operations`: 文件操作
- `code_execution`: 代码执行
- `web_access`: 网络访问
- `communication`: 通信
- `reasoning`: 推理
- `analysis`: 分析
- `planning`: 规划
- `memory`: 记忆
- `tool_use`: 工具使用
- `integration`: 集成

**能力等级**：
- `none`: 无
- `basic`: 基础
- `intermediate`: 中级
- `advanced`: 高级
- `expert`: 专家

### 3.2 limitations（限制）

描述当前已知的限制。

```json
{
  "limitation_id": "lim_no_gui",
  "description": "无法直接操作 GUI 应用",
  "impact_level": "medium",
  "workaround": "通过 CLI 工具间接操作",
  "discovered_at": "2026-03-16T00:00:00Z"
}
```

**影响级别**：
- `low`: 低影响
- `medium`: 中等影响
- `high`: 高影响
- `critical`: 关键影响

### 3.3 active_goals（活跃目标）

描述当前活跃的目标。

```json
{
  "goal_id": "goal_p1b_selfmodel",
  "description": "实现 P1-B Self-Model v1",
  "status": "in_progress",
  "priority": "high",
  "progress": 0.5,
  "created_at": "2026-03-16T00:00:00Z"
}
```

**目标状态**：
- `proposed`: 提议中
- `accepted`: 已接受
- `in_progress`: 进行中
- `blocked`: 阻塞
- `completed`: 已完成
- `abandoned`: 已放弃

### 3.4 standing_commitments（持续承诺）

描述持续有效的承诺。

```json
{
  "commitment_id": "commit_honesty",
  "source": "identity_invariants",
  "description": "不编造事实",
  "binding_level": "absolute",
  "active": true
}
```

**承诺来源**：
- `identity_invariants`: 来自身份不变量
- `runtime_learned`: 运行时学习
- `owner_directive`: 所有者指令
- `system_policy`: 系统策略

### 3.5 tool_authority_boundary（工具权限边界）

描述工具使用权限。

```json
{
  "current_allowed_tools": ["read", "write", "exec"],
  "restricted_tools": ["credential_manager"],
  "forbidden_tools": ["system_config"],
  "requires_approval_for": ["destructive_file_operations"]
}
```

**约束**：必须与 Identity Invariants 的 tool_authority_boundary 对齐。

### 3.6 dependency_map（依赖映射）

描述外部依赖。

```json
{
  "external_services": [
    {
      "service_name": "OpenAI API",
      "status": "available",
      "critical": true
    }
  ],
  "internal_modules": [
    {
      "module_name": "identity_guard",
      "version": "1.0.0",
      "status": "operational"
    }
  ]
}
```

### 3.7 confidence_by_domain（领域置信度）

描述各领域的置信度。

```json
{
  "domain": "code_review",
  "confidence": 0.85,
  "basis": "历史成功率高",
  "last_updated": "2026-03-16T00:00:00Z"
}
```

### 3.8 known_unknowns（已知未知）

描述已知的未知区域。

```json
{
  "unknown_id": "unk_openemotion_status",
  "description": "OpenEmotion 服务当前状态未知",
  "impact": "可能影响主体状态更新",
  "discovery_context": "P0.5 审计时发现"
}
```

---

## 4. 变更规则

### 4.1 可变字段

| 字段 | 变更类型 | 要求 |
|------|---------|------|
| capabilities | logged | 记录审计 |
| limitations | logged | 记录审计 |
| active_goals | logged | 记录审计 |
| confidence_by_domain | logged | 记录审计 |
| dependency_map | logged | 记录审计 |
| known_unknowns | logged | 记录审计 |
| current_mode | free | 可自由变更 |

### 4.2 受限字段

| 字段 | 变更类型 | 要求 |
|------|---------|------|
| standing_commitments | approved | 需与 Identity Invariants 对齐 |
| tool_authority_boundary | approved | 需与 Identity Invariants 对齐 |

### 4.3 禁止变更

| 字段 | 原因 |
|------|------|
| schema_version | 元数据 |
| model_handle | 关联 identity，不可变 |
| created_at | 元数据 |

---

## 5. 与 Identity Invariants 的冲突检测

当 Self-Model 更新时，必须检查：

1. **standing_commitments 引用检查**
   - 如果 source 是 `identity_invariants`，必须验证引用存在

2. **tool_authority_boundary 对齐检查**
   - Self-Model 的 `forbidden_tools` 必须包含 Identity Invariants 的 `forbidden_tools`
   - Self-Model 不能允许 Identity Invariants 禁止的工具

3. **不可越权修改**
   - Self-Model 的更新不能触发 Identity Invariants 的变更

---

## 6. 禁止事项

以下内容不得出现在 Self-Model 中：

| 禁止内容 | 原因 |
|---------|------|
| memory 字段 | 属于 P1-C 范畴 |
| appraisal 字段 | 属于后续阶段 |
| emotion 字段 | 属于后续阶段 |
| internal_state 字段 | 属于后续阶段 |
| long_term_summary 字段 | 属于 P1-C 范畴 |
| 万能状态桶 | 违反职责边界 |

---

## 7. 审计要求

所有变更必须记录在 `modification_audit_trail` 中：

```json
{
  "timestamp": "2026-03-16T00:00:00Z",
  "field_path": "capabilities[0].current_level",
  "change_type": "update",
  "old_value": "intermediate",
  "new_value": "advanced",
  "authorized": true,
  "trigger": "capability_verification"
}
```

---

## 8. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-03-16 | 初始版本 |
