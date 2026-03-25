# 03_BOUNDARY_AND_OWNERSHIP.md

## 双核边界定义

### 核心原则

1. **单一权威源**：每个能力只有一个最终解释权
2. **禁止双主**：允许 mirror / cache / shim，不允许两个系统同时拥有最终解释权
3. **主体本体在 OpenEmotion**：identity / self-model / memory / appraisal / reflection 的本体逻辑必须在 OpenEmotion

### 边界矩阵

| 能力 | OpenEmotion | EgoCore |
|------|-------------|---------|
| identity invariants | ✅ 本体 | ❌ 只读镜像 |
| self-model | ✅ 本体 | ❌ 只读镜像 |
| proto-self kernel | ✅ 本体 | ❌ adapter only |
| memory 本体 | ✅ 本体 | ❌ 只读镜像 |
| appraisal / drive_field | ✅ 本体 | ❌ 只读镜像 |
| reflection | ✅ 本体 | ❌ adapter only |
| cycle 固化 | ✅ 本体 | ❌ 只读镜像 |
| 用户入口 | ❌ | ✅ |
| 运行时 | ❌ | ✅ |
| 工具执行 | ❌ | ✅ |
| trace / replay | ❌ | ✅ |
| 安全边界 | ❌ | ✅ |

## Proto-Self Kernel 边界

### OpenEmotion 侧

- `openemotion/proto_self/` — 所有主体本体语义
- `schemas.py` — KernelEvent / KernelOutput 定义
- `state.py` — ProtoSelfState 状态
- `kernel.py` — process_event 主循环
- `appraisal.py` — drive_field 计算
- `reflection.py` — 反思触发
- `cycles.py` — cycle 固化

### EgoCore 侧（薄 adapter）

- `app/openemotion_adapter/proto_self_adapter.py` — 事件标准化 + kernel 调用
- `app/openemotion_adapter/proto_self_restore.py` — 状态恢复注入
- `app/openemotion_adapter/proto_self_trace_bridge.py` — trace 桥接

### 禁止事项

1. ❌ 在 EgoCore 中实现主体语义
2. ❌ 在 OpenEmotion 中直接执行工具
3. ❌ 在 adapter 中发明新的主体语义
4. ❌ 让 Proto-Self Kernel 直接输出执行命令

## 接口契约

### KernelEvent（输入）

从 EgoCore 到 OpenEmotion的结构化事件：
- event_id, timestamp, actor, source, event_type
- user_intent, raw_text
- task_context, safety_context
- external_result（后果回流）

### KernelOutput（输出）

从 OpenEmotion 到 EgoCore 的结构化结果：
- state_delta（状态增量）
- policy_hint（策略建议）
- response_tendency（响应倾向）
- reflection_note（反思笔记）
- trace_payload（trace 输出）

## 边界宪章

详见：`POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md`

## 边界违规检测

在 `openemotion/proto_self/boundary.py` 中实现：
- `validate_output()` — 检查输出是否越权
- `assert_no_direct_execution()` — 断言无直接执行命令
