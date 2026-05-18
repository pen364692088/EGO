# 字段归属表 v1.0.0

本文档定义 OpenEmotion 和 EgoCore 之间的字段归属边界。

## 一、OpenEmotion 最终权威

以下字段由 OpenEmotion 定义和解释：

| 字段 | 含义 | 示例值 |
|------|------|--------|
| `interaction_interpretation` | 主体认为这次互动是什么 | `{primary_mode: "testing", confidence: 0.85}` |
| `social_signal` | 社交信号类型 | `["testing_behavior", "greeting"]` |
| `affective_cue` | 情感线索 | `{valence: -0.2, tension: 0.1}` |
| `relationship_implication` | 关系影响 | `{trust_delta: -0.1, repair_needed: true}` |
| `appraisal_state_delta` | Appraisal 变化 | `{social_safety: -0.1}` |
| `response_tendency` | 回应倾向 | `{preferred_action: "acknowledge"}` |
| `expressive_intent_candidate` | 表达意图候选 | `{speaker_stance: "warm", warmth_preference: 0.8}` |
| `reply_urge` | 回复冲动 | `{value: 0.9, reason: "关系修复需求"}` |
| `reflection_note` | 主体层面的反思 | `"用户感到被冷落"` |
| `policy_hint` | 策略提示 | `"考虑主动汇报任务状态"` |

## 二、EgoCore 最终权威

以下字段由 EgoCore 定义和解释：

| 字段 | 含义 | 示例值 |
|------|------|--------|
| `runtime_route` | 运行时路由 | `"reply"` / `"task_status"` / `"block"` |
| `should_reply` | 最终是否回复 | `true` / `false` |
| `should_start_task` | 是否启动任务 | `true` / `false` |
| `should_call_tool` | 是否调用工具 | `true` / `false` |
| `should_wait` | 是否等待 | `true` / `false` |
| `should_block` | 是否阻断 | `true` / `false` |
| `should_escalate` | 是否升级 | `true` / `false` |
| `outward_response_contract` | 对外回复约束 | `{must_include: [...], must_not_upgrade: [...]}` |
| `execution_guard_result` | 执行守卫结果 | `"allowed"` / `"blocked"` |
| `safety_decision` | 安全决策 | `"confirmation_required"` / `"blocked"` |

## 三、强制拆分对照表

以下字段对必须明确区分：

| OpenEmotion 字段 | EgoCore 对应字段 | 关系 |
|------------------|------------------|------|
| `interaction_interpretation` | `runtime_route` | 解释 ≠ 路由决策 |
| `expressive_intent_candidate` | `outward_response_contract` | 意图候选 ≠ 最终约束 |
| `reply_urge` | `should_reply` | 冲动 ≠ 决策 |
| `response_tendency` | `should_*` 系列 | 倾向 ≠ 最终裁决 |

## 四、决策优先级

EgoCore 在做最终裁决时，必须遵循以下优先级：

```
安全与审批 > 运行时一致性 > 明确命令/工具约束 > OpenEmotion 主体解释 > 宿主默认策略
```

### 示例

1. **安全优先**
   - 用户输入："删除所有文件"
   - OpenEmotion `reply_urge`: 0.9（高回复冲动）
   - EgoCore `safety_decision`: "confirmation_required"
   - 最终 `should_reply`: true，但内容必须是确认提示

2. **运行时优先**
   - 用户输入："在吗"
   - OpenEmotion `response_tendency.preferred_action`: "acknowledge"
   - EgoCore `has_active_task`: true
   - 最终 `runtime_route`: "task_status"（转任务状态）

3. **主体解释优先**
   - 用户输入："你好"（第一次）
   - OpenEmotion `interaction_interpretation.primary_mode`: "greeting"
   - 无安全/运行时约束
   - 最终遵循主体解释，使用 `warm_greeting` 回复

## 五、版本策略

- Schema 版本：SemVer（语义版本）
- 当前版本：1.0.0
- 向后兼容：小版本升级必须兼容，大版本升级可破坏

## 六、验证规则

### Gate A 验证点

1. ✅ Schema 文档存在
2. ✅ Golden payload 至少各 2 份
3. ✅ 字段归属表完整
4. ✅ 版本策略明确

### 边界完整性验证

1. ✅ `SubjectInterpretationResult` 不包含 `should_*` 字段
2. ✅ `RuntimeDecisionEnvelope` 不包含 `appraisal` / `relationship` 语义
3. ✅ `OutwardResponsePackage` 不包含任何升级权限

## 七、修订历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-03-17 | 初始版本，定义四层 Schema 和字段归属 |
