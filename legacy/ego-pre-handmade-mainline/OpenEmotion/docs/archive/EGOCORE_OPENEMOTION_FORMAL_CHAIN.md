# EgoCore ↔ OpenEmotion 正式主链定义

## 正式架构

```
┌─────────────────────────────────────────────────────────────┐
│                        EgoCore                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  入口层     │  │  运行时     │  │  OpenEmotion       │  │
│  │  Telegram   │→ │  Session    │→ │  Adapter           │  │
│  │  CLI        │  │  Task       │  │  (egocore/adapters)│  │
│  │  API        │  │  Tools      │  └─────────┬───────────┘  │
│  └─────────────┘  └─────────────┘            │              │
└──────────────────────────────────────────────┼──────────────┘
                                               │ HTTP/模块直连
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    OpenEmotion (emotiond)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Identity   │  │  Memory     │  │  Appraisal          │  │
│  │  Invariants │  │  Evolution  │  │  State              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Self-Model │  │  Reflection │  │  Response           │  │
│  │             │  │  Engine     │  │  Tendency           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 职责边界

### EgoCore 负责（宿主）

| 层 | 职责 |
|---|------|
| 入口 | 用户消息接收、渠道接入、消息解析 |
| 运行时 | Session 管理、Task 调度、生命周期 |
| 执行 | 工具调用、权限控制、安全边界 |
| 宿主 | OpenEmotion adapter、状态承接 |
| 裁决 | 最终外部决策、高风险动作审批 |
| 审计 | Replay、Trace、Artifact 落盘 |

### OpenEmotion 负责（被宿主）

| 层 | 职责 |
|---|------|
| 身份 | Identity invariants、连续性 |
| 模型 | Self-model 演化、能力评估 |
| 记忆 | Memory evolution、叙事构建 |
| 评价 | Appraisal、情感状态 |
| 反思 | Reflection、策略提炼 |
| 倾向 | Response tendency、行为偏好 |

### 明确禁止

- ❌ EgoCore 私自实现 identity/memory/appraisal 本体逻辑
- ❌ OpenEmotion 直接接入 Telegram/渠道
- ❌ OpenEmotion 直接执行工具
- ❌ OpenEmotion 直接审批高风险动作

## 接口契约

### EgoCore → OpenEmotion (oe.event.v1)

```json
{
  "schema_version": "1.0.0",
  "event_id": "evt_xxx",
  "timestamp": "2026-03-17T00:00:00Z",
  "actor": {"actor_id": "user_id", "actor_type": "user"},
  "source": {"channel": "telegram", "surface": "dm"},
  "event_type": "user_message",
  "user_intent": {"primary_intent": "chat", "raw_input": "..."},
  "conversation_context": {...},
  "task_context": {...},
  "runtime_summary": {...},
  "safety_context": {"risk_level": "low"},
  "external_result": null
}
```

### OpenEmotion → EgoCore (oe.result.v1)

```json
{
  "schema_version": "1.0.0",
  "output_id": "out_xxx",
  "event_id_ref": "evt_xxx",
  "identity_state_delta": {...},
  "self_model_delta": {...},
  "memory_update": {...},
  "relationship_update": {...},
  "appraisal_state_delta": {...},
  "reflection_note": {...},
  "policy_hint": {...},
  "response_tendency": {...},
  "confidence_metadata": {...}
}
```

## Artifact 规范

每次真实请求必须保存：

| 文件 | 内容 |
|------|------|
| `raw_ingress_event.json` | 原始入口事件 |
| `normalized_event.json` | 标准化后事件 |
| `openemotion_request.json` | 发送给 OpenEmotion 的请求 |
| `openemotion_response.json` | OpenEmotion 返回的响应 |
| `runtime_decision.json` | EgoCore 最终决策 |
| `outbound_message.json` | 发送给用户的回复 |

若有工具执行，追加：
| `external_result_event.json` | 执行结果回流事件 |

## 验收标准

### Gate A: Contract
- [ ] oe.event.v1 schema 完整
- [ ] oe.result.v1 schema 完整
- [ ] 示例 payload 可回放

### Gate B: E2E
- [ ] 普通聊天场景通过
- [ ] 跨轮记忆场景通过
- [ ] 结果回流场景通过

### Gate C: Boundary
- [ ] EgoCore 无主体本体逻辑
- [ ] OpenEmotion 无渠道/工具/审批
- [ ] Artifact 齐全

---

**创建日期**: 2026-03-17
**状态**: 正式生效
