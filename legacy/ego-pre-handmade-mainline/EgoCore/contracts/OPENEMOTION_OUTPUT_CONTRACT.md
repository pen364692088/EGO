# OpenEmotion Output Contract v1

> 版本: 1.0.0
> 日期: 2026-03-16
> 状态: Draft

## 概述

本文档定义 OpenEmotion 返回给 EgoCore 的标准化输出契约。

**目的**：让 OpenEmotion 的输出能够被 EgoCore 结构化消费，形成稳定的主宿主接口。

## 核心原则

1. **可消费性**：输出格式对 EgoCore 可直接解析和消费
2. **增量性**：使用 delta 模式，只传递变化
3. **可追溯**：output_id + event_id_ref 关联输入输出
4. **置信度透明**：所有关键输出都有置信度标注

## 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `output_id` | string | 输出唯一标识 |
| `timestamp` | ISO8601 | 输出时间 |
| `event_id_ref` | string | 关联的输入事件 ID |
| `confidence_metadata` | object | 置信度元数据 |

## 输出模块

### 1. 身份状态变化 (`identity_state_delta`)

记录身份层面的变化：
- 名称/角色变化
- 承诺增减
- 不变量违反检测

### 2. 自我模型变化 (`self_model_delta`)

记录自我认知更新：
- 能力置信度更新
- 目标增减
- 局限性认识

### 3. 记忆更新 (`memory_update`)

三层记忆更新：
- **事件记忆**：带显著性的事件记录
- **叙事记忆**：形成的故事线
- **策略记忆**：沉淀的策略

### 4. 关系更新 (`relationship_update`)

对象特异性关系变化：
- 信任度变化
- 依恋度变化
- 交互统计

### 5. 评价状态变化 (`appraisal_state_delta`)

内部状态变化：
- 效价 (valence): 负-中性-正
- 唤醒度 (arousal): 激活程度
- 支配度 (dominance): 控制感
- 维度评分：目标支持、来源可信度等

### 6. 反思笔记 (`reflection_note`)

失败/偏差后的反思：
- 观察 → 诊断 → 策略候选
- 是否提升到长期记忆

### 7. 策略提示 (`policy_hint`)

给 EgoCore 的行为建议：
- 偏好行动类型
- 风险容忍度
- 约束建议

### 8. 响应倾向 (`response_tendency`)

影响外部响应的参数：
- 语气倾向
- 详细程度
- 主动程度
- 情感表达程度

## 示例输出

### 示例 1: 用户支持后的正向响应

```json
{
  "output_id": "out_20260316_positive_001",
  "timestamp": "2026-03-16T02:00:00Z",
  "event_id_ref": "evt_20260316_user_msg_001",
  "identity_state_delta": {
    "name_changed": false,
    "role_changed": false
  },
  "relationship_update": {
    "actor_ref": "user_moonlight",
    "trust_delta": 0.05,
    "attachment_delta": 0.02,
    "last_interaction_summary": "用户请求代码审查，配合度高"
  },
  "appraisal_state_delta": {
    "valence": 0.3,
    "arousal": 0.4,
    "dominance": 0.6,
    "dimensions": {
      "goal_support": 0.5,
      "source_credibility": 0.8,
      "expectation_violation": 0.0,
      "fairness": 0.5,
      "threat_level": 0.0
    }
  },
  "memory_update": {
    "event_memory_additions": [
      {
        "event_ref": "evt_20260316_user_msg_001",
        "salience": 0.6,
        "tags": ["task_request", "code_review", "cooperative"]
      }
    ]
  },
  "policy_hint": {
    "preferred_action_type": "respond",
    "risk_tolerance": "moderate"
  },
  "response_tendency": {
    "tone": "warm",
    "verbosity": "moderate",
    "proactivity": 0.7,
    "emotional_expressiveness": 0.3
  },
  "confidence_metadata": {
    "overall_confidence": 0.85,
    "identity_confidence": 0.95,
    "memory_confidence": 0.8,
    "policy_confidence": 0.75
  }
}
```

### 示例 2: 任务失败后的反思

```json
{
  "output_id": "out_20260316_reflection_001",
  "timestamp": "2026-03-16T02:30:00Z",
  "event_id_ref": "evt_20260316_task_fail_001",
  "appraisal_state_delta": {
    "valence": -0.2,
    "arousal": 0.6,
    "dominance": 0.4,
    "dimensions": {
      "goal_support": -0.3,
      "expectation_violation": 0.5,
      "threat_level": 0.1
    }
  },
  "reflection_note": {
    "observation": "工具调用超时，可能由于网络问题",
    "diagnosis": "外部服务不稳定，需要重试机制",
    "policy_candidate": "对不稳定外部服务添加 fallback 策略",
    "confidence": 0.7,
    "promote_to_memory": true
  },
  "policy_hint": {
    "preferred_action_type": "act",
    "risk_tolerance": "conservative",
    "constraints": ["retry_with_backoff", "notify_user"]
  },
  "response_tendency": {
    "tone": "neutral",
    "verbosity": "moderate",
    "proactivity": 0.8
  },
  "confidence_metadata": {
    "overall_confidence": 0.7,
    "uncertainty_reasons": ["外部服务状态未知"]
  }
}
```

### 示例 3: 空输出（无变化）

```json
{
  "output_id": "out_20260316_noop_001",
  "timestamp": "2026-03-16T03:00:00Z",
  "event_id_ref": "evt_20260316_system_001",
  "confidence_metadata": {
    "overall_confidence": 1.0,
    "uncertainty_reasons": []
  }
}
```

## 消费方（EgoCore）责任

1. **验证格式**：所有输出必须通过 JSON Schema 验证
2. **应用变化**：按 delta 更新本地状态
3. **记录审计**：保存输出作为审计线索
4. **失败处理**：输出验证失败时降级处理

## 版本管理

- Schema 版本在 `$id` 中体现
- 新增可选字段视为兼容
- 必填字段变化需要升级主版本号

## 下一步

- [ ] 实现 OpenEmotion Adapter 消费接口
- [ ] 集成测试验证
- [ ] 生产环境试点
