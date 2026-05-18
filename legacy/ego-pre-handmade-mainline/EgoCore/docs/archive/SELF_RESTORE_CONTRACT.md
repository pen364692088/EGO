# Self Restore Contract v1

> 版本: 1.0.0
> 日期: 2026-03-16
> 类型: 自我恢复机制

---

## 1. 概述

Self Restore 定义新会话启动时的主体恢复流程，确保跨会话的连续性。

**核心原则**：
- Restore 是加载过程，不是创建过程
- Restore 从持久化文件加载，不从 cache 恢复
- Restore 必须校验三层一致性
- Restore 失败必须有明确错误出口

---

## 2. 恢复流程

### 2.1 标准恢复流程

```
新会话启动
    ↓
检查持久化文件存在
    ↓
加载 Identity Invariants
    ↓
加载 Self-Model
    ↓
加载 Long-Term Self Summary
    ↓
校验三层一致性
    ↓
处理冲突（如果有）
    ↓
注入 Runtime Context
    ↓
记录 Restore Audit
    ↓
恢复完成
```

### 2.2 恢复顺序

必须按以下顺序加载：

1. **Identity Invariants**（第一层）
   - 基础身份定义
   - 其他层引用此层

2. **Self-Model**（第二层）
   - 引用 identity_handle
   - 需要与 identity 对齐

3. **Long-Term Self Summary**（第三层）
   - 引用 identity 和 self-model
   - 需要与两者对齐

---

## 3. 一致性校验

### 3.1 Identity ↔ Self-Model 校验

| 校验项 | 规则 | 失败处理 |
|-------|------|---------|
| model_handle | 必须等于 identity_handle | 错误：身份不匹配 |
| tool_authority_boundary | forbidden_tools 必须一致 | 警告：权限不一致 |

### 3.2 Identity ↔ Summary 校验

| 校验项 | 规则 | 失败处理 |
|-------|------|---------|
| identity_handle_ref | 必须等于 identity_handle | 错误：身份不匹配 |
| core_role | 必须一致 | 错误：角色不一致 |

### 3.3 Self-Model ↔ Summary 校验

| 校验项 | 规则 | 失败处理 |
|-------|------|---------|
| model_handle | 必须一致 | 错误：模型不匹配 |
| snapshot_timestamp | 必须有效 | 警告：快照过期 |

---

## 4. 冲突处理

### 4.1 冲突级别

| 级别 | 说明 | 处理方式 |
|------|------|---------|
| ERROR | 阻塞性冲突 | 中止恢复，返回错误 |
| WARNING | 非阻塞性冲突 | 记录警告，继续恢复 |
| INFO | 信息提示 | 记录日志，继续恢复 |

### 4.2 冲突处理策略

| 冲突类型 | 处理策略 |
|---------|---------|
| 身份不匹配 | 以 identity invariants 为准，中止恢复 |
| 角色不一致 | 以 identity invariants 为准，标记 self-model 需更新 |
| 权限不一致 | 以 identity invariants 为准，标记 self-model 需更新 |
| 快照过期 | 继续恢复，标记 summary 需刷新 |

---

## 5. 缺失降级

当部分文件缺失时：

### 5.1 Identity Invariants 缺失

**处理**：中止恢复，返回错误
**原因**：身份是基础，必须存在

### 5.2 Self-Model 缺失

**处理**：降级恢复
**行为**：
- 加载 identity invariants
- 创建空 self-model（基于 identity）
- 标记需要初始化 self-model

### 5.3 Summary 缺失

**处理**：降级恢复
**行为**：
- 加载 identity invariants 和 self-model
- 跳过 summary 恢复
- 标记需要生成 summary

---

## 6. Runtime Context 注入

恢复完成后，将以下内容注入 runtime：

### 6.1 注入内容

| 内容 | 来源 |
|------|------|
| identity | Identity Invariants |
| capabilities | Self-Model.capabilities |
| limitations | Self-Model.limitations |
| active_goals | Self-Model.active_goals |
| commitments | Identity Invariants + Self-Model |
| recovery_context | Summary.recovery_hints |

### 6.2 注入规则

- 不覆盖现有 runtime 状态
- 只注入已验证的内容
- 记录注入审计

---

## 7. Restore Audit

### 7.1 审计内容

```json
{
  "restore_id": "restore_20260316_xxx",
  "timestamp": "...",
  "session_id": "...",
  "status": "success|partial|failed",
  "loaded_layers": ["identity", "self_model", "summary"],
  "conflicts": [],
  "warnings": [],
  "errors": [],
  "duration_ms": 123
}
```

### 7.2 审计保存

- 每次恢复都生成审计记录
- 保存到 `artifacts/restore/audit/`
- 失败记录单独保存

---

## 8. 禁止事项

| 禁止内容 | 原因 |
|---------|------|
| memory evolution | 属于 P2 范畴 |
| appraisal/internal_state | 属于后续阶段 |
| reflection/policy promotion | 属于后续阶段 |
| prompt 拼接替代 restore | 不是结构化机制 |
| runtime cache 作为真相源 | cache 是临时状态 |
| 跳过校验 | 破坏一致性保证 |

---

## 9. 恢复状态

| 状态 | 说明 |
|------|------|
| success | 全部三层加载成功，无冲突 |
| partial | 部分层加载成功，有降级 |
| failed | 恢复失败，需要人工介入 |

---

## 10. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-03-16 | 初始版本 |
