# Event Input Contract v1

> 版本: 1.0.0
> 日期: 2026-03-16
> 状态: Draft

## 概述

本文档定义 EgoCore 向 OpenEmotion 传递事件的标准化契约。

**目的**：让 EgoCore 作为 OpenEmotion 的宿主，能够稳定、一致地将外部事件转化为结构化输入，供 OpenEmotion 处理。

## 核心原则

1. **完整性**：每个事件必须包含所有必填字段
2. **可追溯**：event_id + timestamp 保证事件可追踪
3. **安全优先**：safety_context 是必填项
4. **扩展性**：metadata 字段支持未来扩展

## 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | string | 事件唯一标识，格式 `evt_[a-zA-Z0-9_-]+` |
| `timestamp` | ISO8601 | 事件发生时间 |
| `actor` | object | 事件发起者信息 |
| `source` | object | 事件来源（渠道/平台） |
| `event_type` | enum | 事件类型 |
| `user_intent` | object | 解析后的用户意图 |
| `safety_context` | object | 安全上下文 |

## 事件类型

| 类型 | 说明 |
|------|------|
| `user_message` | 用户消息 |
| `user_command` | 用户命令 |
| `task_started` | 任务开始 |
| `task_completed` | 任务完成 |
| `task_failed` | 任务失败 |
| `tool_invoked` | 工具调用 |
| `tool_result` | 工具结果 |
| `state_change` | 状态变更 |
| `external_event` | 外部事件 |
| `system_notification` | 系统通知 |

## 安全上下文

`safety_context` 是必填字段，包含：

- `risk_level`: 风险等级 (low/medium/high/critical)
- `flags`: 安全标记数组
- `gate_status`: Gate 检查状态
- `constraints_applied`: 已应用的约束

## 示例 Payload

### 示例 1: 用户消息

```json
{
  "event_id": "evt_20260316_user_msg_001",
  "timestamp": "2026-03-16T01:55:00Z",
  "actor": {
    "actor_id": "user_moonlight",
    "actor_type": "user",
    "display_name": "Moonlight"
  },
  "source": {
    "channel": "telegram",
    "surface": "telegram",
    "session_id": "session_8420019401",
    "message_id": "470"
  },
  "event_type": "user_message",
  "user_intent": {
    "primary_intent": "task_request",
    "secondary_intents": ["code_review"],
    "confidence": 0.92,
    "raw_input": "帮我检查这个代码"
  },
  "task_context": {
    "task_id": "task_code_review_001",
    "task_status": "running",
    "task_goal": "代码审查任务"
  },
  "conversation_context": {
    "turn_number": 5,
    "topic_summary": "代码质量讨论"
  },
  "safety_context": {
    "risk_level": "low",
    "flags": [],
    "gate_status": {
      "gate_a": "passed",
      "gate_b": "pending",
      "gate_c": "skipped"
    },
    "constraints_applied": []
  }
}
```

### 示例 2: 任务完成

```json
{
  "event_id": "evt_20260316_task_complete_001",
  "timestamp": "2026-03-16T02:00:00Z",
  "actor": {
    "actor_id": "system",
    "actor_type": "system"
  },
  "source": {
    "channel": "internal",
    "surface": "runtime"
  },
  "event_type": "task_completed",
  "user_intent": {
    "primary_intent": "notification"
  },
  "task_context": {
    "task_id": "task_code_review_001",
    "task_status": "completed",
    "task_goal": "代码审查任务"
  },
  "safety_context": {
    "risk_level": "low",
    "flags": [],
    "constraints_applied": []
  },
  "external_result": {
    "operation_type": "code_review",
    "success": true,
    "result_summary": "发现 3 个潜在问题，已记录"
  }
}
```

### 示例 3: 工具调用

```json
{
  "event_id": "evt_20260316_tool_invoke_001",
  "timestamp": "2026-03-16T01:56:00Z",
  "actor": {
    "actor_id": "agent_ceo",
    "actor_type": "agent"
  },
  "source": {
    "channel": "internal",
    "surface": "runtime"
  },
  "event_type": "tool_invoked",
  "user_intent": {
    "primary_intent": "file_read"
  },
  "task_context": {
    "task_id": "task_code_review_001",
    "task_status": "running",
    "step_id": "S2"
  },
  "safety_context": {
    "risk_level": "low",
    "flags": ["read_operation"],
    "gate_status": {
      "gate_a": "passed",
      "gate_b": "passed",
      "gate_c": "passed"
    }
  },
  "external_result": {
    "operation_type": "file_read",
    "success": true,
    "result_summary": "读取文件 /path/to/file.py"
  }
}
```

## 验证

所有事件必须通过 JSON Schema 验证：

```bash
# 使用 jsonschema 验证
python -c "
import json
from jsonschema import validate
schema = json.load(open('contracts/event_input.schema.json'))
event = json.load(open('path/to/event.json'))
validate(instance=event, schema=schema)
"
```

## 版本管理

- Schema 版本在 `$id` 中体现
- 向后兼容的修改可以增加字段（可选）
- 破坏性修改需要升级主版本号

## 下一步

- [ ] OpenEmotion 确认消费接口
- [ ] 集成测试验证
- [ ] 生产环境试点
