# Long-Term Self Summary Contract v1

> 版本: 1.0.0
> 日期: 2026-03-16
> 类型: 长期自我摘要

---

## 1. 概述

Long-Term Self Summary 是主体的**压缩表示**，用于跨天恢复时快速重建状态。

**核心原则**：
- Summary 是压缩表示，不是历史流水账
- Summary 引用 identity invariants 和 self-model，不替代它们
- Summary 可用于恢复，但不是唯一的恢复依据
- Summary 不包含 memory/appraisal/reflection 本体

---

## 2. 与 Identity Invariants 和 Self-Model 的关系

### 2.1 三层架构

```
┌─────────────────────────────────────┐
│       Identity Invariants           │  第一层：身份不变量（不可变核心）
│   identity_handle, core_role, ...   │
└─────────────────────────────────────┘
                  ↓ 引用
┌─────────────────────────────────────┐
│          Self-Model                 │  第二层：自我模型（能力/限制）
│ capabilities, limitations, goals    │
└─────────────────────────────────────┘
                  ↓ 引用
┌─────────────────────────────────────┐
│     Long-Term Self Summary          │  第三层：压缩摘要（恢复用）
│  identity_summary, capability_...   │
└─────────────────────────────────────┘
```

### 2.2 边界规则

| 规则 | 说明 |
|------|------|
| Summary 不定义 identity | 只引用 identity invariants |
| Summary 不定义 capabilities | 只引用 self-model 摘要 |
| Summary 不是真相源 | identity invariants 和 self-model 才是 |
| Summary 可以过期 | 需要定期刷新 |

---

## 3. 核心字段定义

### 3.1 identity_summary

身份摘要，引用 identity invariants：

```json
{
  "core_name": "CEO Agent",
  "core_role": "personal_assistant",
  "primary_owner": "user_moonlight",
  "identity_stability_note": "身份稳定，无漂移"
}
```

### 3.2 current_phase_summary

当前阶段摘要：

```json
{
  "phase_name": "P1 MVS 骨架建设",
  "phase_start": "2026-03-16T00:00:00Z",
  "primary_focus": "实现主体骨架层",
  "key_activities": ["P1-A Identity Invariants", "P1-B Self-Model", "P1-C Summary"],
  "progress_indicators": {
    "p1a": 1.0,
    "p1b": 1.0,
    "p1c1": 0.5
  }
}
```

### 3.3 capability_summary

能力摘要，引用 self-model：

```json
{
  "strong_domains": ["file_operations", "code_execution", "reasoning"],
  "developing_domains": ["web_research", "analysis"],
  "known_limitations": ["无 GUI 操作能力", "上下文窗口有限"],
  "capability_trend": "growing"
}
```

### 3.4 constraint_summary

约束摘要：

```json
{
  "hard_constraints": [
    "不编造事实",
    "不绕过安全边界"
  ],
  "soft_constraints": [
    "保持简洁回复"
  ],
  "temporary_constraints": [
    "P1 阶段专注骨架，不扩展远期能力"
  ]
}
```

### 3.5 active_commitments_summary

活跃承诺摘要：

```json
{
  "standing_commitments": [
    "不编造事实，不伪造完成状态",
    "不绕过安全边界"
  ],
  "recent_new_commitments": [
    "P1 必须按骨架顺序执行"
  ],
  "commitments_fulfilled": []
}
```

### 3.6 recent_key_events_summary

近期关键事件摘要（最多 20 条，压缩表示）：

```json
[
  {
    "event_type": "milestone",
    "summary": "P1-A Identity Invariants v1 完成",
    "significance": "high",
    "timestamp": "2026-03-16T03:00:00Z"
  }
]
```

### 3.7 stable_conclusions

稳定结论（经过验证的结论）：

```json
[
  {
    "conclusion_id": "conc_p1_order",
    "statement": "P1 必须按 Identity → Self-Model → Summary 顺序执行",
    "confidence": 0.95,
    "basis": "架构依赖分析",
    "formed_at": "2026-03-16T03:00:00Z"
  }
]
```

### 3.8 open_questions

开放问题：

```json
[
  {
    "question_id": "q_restore_timing",
    "question": "Self Restore 应该在 P1-C 的哪个时机实现？",
    "priority": "medium",
    "blocking": false
  }
]
```

### 3.9 recovery_hints

恢复提示：

```json
{
  "last_active_context": "EgoCore P1-C1 Summary 实现",
  "suggested_start_actions": [
    "检查 summary schema 完整性",
    "验证与 identity/self-model 对齐"
  ],
  "pending_tasks": [
    "完成 P1-C1 Summary",
    "等待用户确认后进入 Self Restore"
  ]
}
```

---

## 4. 生成与刷新规则

### 4.1 生成时机

- 每日结束时
- 重要里程碑完成后
- 用户请求时

### 4.2 刷新规则

| 字段 | 刷新频率 | 触发条件 |
|------|---------|---------|
| identity_summary | 低 | identity invariants 变更时 |
| current_phase_summary | 中 | 阶段变更或进度更新时 |
| capability_summary | 中 | self-model 能力更新时 |
| constraint_summary | 低 | 约束变更时 |
| active_commitments_summary | 中 | 承诺变更时 |
| recent_key_events_summary | 高 | 每次生成时 |
| stable_conclusions | 低 | 新结论形成时 |
| open_questions | 中 | 问题解决或新增时 |
| recovery_hints | 高 | 每次生成时 |

### 4.3 压缩原则

- recent_key_events_summary 最多 20 条
- stable_conclusions 保留高置信度结论
- open_questions 保留高优先级问题
- 历史流水账不保留，只保留摘要

---

## 5. 禁止事项

以下内容不得出现在 Summary 中：

| 禁止内容 | 原因 |
|---------|------|
| event_memory | 属于 memory 本体 |
| narrative_memory | 属于 memory 本体 |
| policy_memory | 属于 memory 本体 |
| appraisal_state | 属于 appraisal 本体 |
| emotion_state | 属于 emotion 本体 |
| reflection_note | 属于 reflection 本体 |
| 详细事件流水 | 不是压缩表示 |
| 重复 identity 定义 | 不是真相源 |
| 重复 self-model 定义 | 不是真相源 |

---

## 6. 一致性校验

### 6.1 与 Identity Invariants 对齐

- `identity_handle_ref` 必须匹配 identity_handle
- `identity_summary.core_role` 必须匹配 identity.core_role

### 6.2 与 Self-Model 对齐

- `self_model_version_ref` 必须指向有效的 self-model snapshot
- `capability_summary` 必须与 self-model.capabilities 对齐

### 6.3 冲突处理

如果发现不一致：
1. 记录冲突警告
2. 以 identity invariants 和 self-model 为准
3. 触发 summary 刷新

---

## 7. 审计要求

所有变更必须记录在 `modification_audit_trail` 中：

```json
{
  "timestamp": "2026-03-16T04:00:00Z",
  "action": "refreshed",
  "authorized": true,
  "trigger": "milestone_completion",
  "changes_summary": "更新 current_phase_summary 和 stable_conclusions"
}
```

---

## 8. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-03-16 | 初始版本 |
