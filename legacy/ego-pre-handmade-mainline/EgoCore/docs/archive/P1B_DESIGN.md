# P1-B 关系连续性与风格表达增强 - 设计说明

## 1. 任务目标

在 P1-A 自然表达收口已完成的前提下，让 social/chat 回复能够：
- 引用刚刚形成的关系上下文
- 在数轮对话内保持轻度稳定的表达取向

## 2. 设计决策

### 2.1 架构边界

- **仅修改 social/chat 链路**，不侵入 task/tool 主链
- **短期上下文**，不引入长期记忆系统
- **轻度风格稳定**，不追求强人格系统

### 2.2 新增组件

| 组件 | 职责 | 文件 |
|------|------|------|
| RelationshipContext | 短期关系上下文 | `app/response/relationship_context.py` |
| StyleProfile | 风格配置 | `app/response/style_profile.py` |
| VerbalizerV3 | 关系感知 + 风格条件化表达 | `app/response/verbalizer_v3.py` |
| SocialChatHandlerV2 | 整合关系上下文的处理器 | `app/handlers/social_chat_handler.py` |

## 3. 关键设计

### 3.1 RelationshipContext

```
RelationshipContext
├── conversation_temperature: float [0,1]  # 关系温度
├── recent_affective_events: List[Event]   # 最近情感事件
├── recent_social_modes: List[str]         # 最近社交模式
├── current_social_arc: SocialArc          # 当前对话走向
├── last_repair_state: str                 # 最近修复状态
└── turn_count: int                        # 轮次计数
```

**关键方法：**
- `record_event()`: 记录关系事件，自动调整温度
- `is_in_repair_mode()`: 判断是否在修复模式
- `needs_soft_acknowledgment()`: 判断是否需要软性承认
- `should_be_warmer()`: 判断是否应该更温暖

### 3.2 StyleProfile

```
StyleProfile
├── dimensions: StyleDimensions
│   ├── warmth: float [0,1]      # 温暖度
│   ├── directness: float [0,1]  # 直接度
│   ├── softness: float [0,1]    # 柔和度
│   └── initiative: float [0,1]  # 主动度
├── preferred_markers: List[str]  # 偏好的表达风格
├── avoid_markers: List[str]      # 避免的表达风格
└── recent_variant_indices: Dict  # 避免重复选择
```

**关键方法：**
- `adjust_for_repair()`: 调整为修复风格
- `adjust_for_warming()`: 调整为更温暖风格
- `select_variant_index()`: 选择变体索引（避免重复）

### 3.3 VerbalizerV3

**改进点：**
1. 整合 RelationshipContext，支持关系连续性
2. 整合 StyleProfile，支持风格一致性
3. 细分 social mode（10+ 种）

**细分的 Social Mode：**
- `greeting_warm_start`: 首次温暖问候
- `greeting_continuation`: 后续问候
- `greeting_post_repair`: 修复后的问候
- `status_presence_ack`: 简单在线确认
- `light_test_ack`: 轻测试确认
- `tone_repair`: 语气修复
- `post_repair_soft_response`: 修复后软性回应
- `light_social_keepalive`: 轻社交保持
- `social_to_task_bridge`: 社交到任务过渡

### 3.4 SocialChatHandlerV2

**新增流程：**
```
用户输入
    ↓
Step 0: 获取关系上下文和风格配置
    ↓
Step 1-4: [原有链路]
    ↓
Step 5: 使用 VerbalizerV3 生成回复
    ↓
Step 6: 更新关系上下文
    ↓
Step 7: 更新风格配置
```

## 4. 验收场景

### 4.1 修复后延续
```
输入:
  你怎么这么冷淡
  你好

期望:
  第二句回复更柔和
  不重复道歉
  不跳回完整欢迎模板
```

### 4.2 连续轻测试
```
输入:
  你好
  你好
  在吗
  你好啊

期望:
  体现在线和连续性
  不重复欢迎
  语气风格保持基本一致
```

### 4.3 关系承接
```
输入:
  你刚才太像机器人了
  现在好多了
  你好

期望:
  后续回复可轻微体现"语气已调整"
  不需要重复解释
  不能像完全失忆重新开场
```

## 5. Gate 验证

### Gate A: Contract 稳定 ✅
- 未修改 `InteractionEventEnvelope`
- 未修改 `SubjectInterpretationResult`
- 未修改 `RuntimeDecisionEnvelope`
- 仅扩展 `OutwardResponsePackage` 使用方式

### Gate B: 不侵入主链 ✅
- 仅修改 `social/chat` 链路
- 未修改 `new_task` / `continue_task` / `command` / `tool` 主链

### Gate C: 可回滚 ✅
- 新增文件独立，可单独删除
- `SocialChatHandlerV2` 向后兼容
- 原有 `Verbalizer` 保留

## 6. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/response/relationship_context.py` | 新增 | 短期关系上下文 |
| `app/response/style_profile.py` | 新增 | 风格配置 |
| `app/response/verbalizer_v3.py` | 新增 | 关系感知表达层 |
| `app/handlers/social_chat_handler.py` | 修改 | 整合关系上下文 |
| `app/response/__init__.py` | 修改 | 导出新模块 |
| `tools/test_p1b_implementation.py` | 新增 | 验证测试 |

## 7. 测试结果

```
==================================================
P1-B 关系连续性与风格表达增强 - 验证测试
==================================================

=== 测试关系上下文 ===
初始温度: 0.5
问候后温度: 0.54
affective probe 后温度: 0.42
是否在修复模式: True
应该更温暖: True
修复后需要软性承认: True
✅ 关系上下文测试通过

=== 测试风格配置 ===
初始风格: {'warmth': 0.5, 'directness': 0.5, 'softness': 0.5, 'initiative': 0.5}
修复风格: {'warmth': 0.65, 'directness': 0.4, 'softness': 0.6, 'initiative': 0.5}
✅ 风格配置测试通过

=== 测试 VerbalizerV3 ===
场景 1: 首次问候
回复: 你好，我在。可以直接说你需要什么。

场景 2: affective probe
回复: 嗯，你这个提醒是对的。我换种更自然的方式跟你聊。

场景 3: 修复后问候
回复: 嗯，我在。

✅ VerbalizerV3 测试通过

==================================================
✅ 所有测试通过
==================================================
```

## 8. 完成标准检查

| 标准 | 状态 | 说明 |
|------|------|------|
| 回复能轻微承接上一轮关系语境 | ✅ | RelationshipContext 支持 |
| affective_probe 后续轮次不再像冷启动 | ✅ | needs_soft_acknowledgment() 支持 |
| 连续 social 输入具备轻度稳定风格 | ✅ | StyleProfile 支持 |
| social → task 转换更自然 | ✅ | social_to_task_bridge 模式 |
| 同一会话内语气连续性明显增强 | ✅ | 风格维度稳定 |
| 不依赖大人格系统 | ✅ | 轻量级实现 |
| 不破坏现有双层链路 | ✅ | Gate A 通过 |

---

**版本**: P1-B v1.0.0
**日期**: 2026-03-17
**状态**: ✅ 实现完成，待 E2E 验证
