# EgoCore 宿主化 OpenEmotion 进展

## 当前状态

**日期**: 2026-03-17
**阶段**: v6k.prehost / bootstrap-hosting

## 已完成

### 1. 基础设施
- [x] emotiond 服务配置为 systemd 用户服务
- [x] 开机自启已启用
- [x] 服务运行在 http://127.0.0.1:18080

### 2. 接口契约
- [x] EgoCore event_input.schema.json (v1.0.0)
- [x] EgoCore openemotion_output.schema.json (v1.0.0)
- [x] 转换逻辑: EventInput.to_openemotion_event()

### 3. OpenClaw 集成
- [x] emotiond 扩展已配置 (~/.openclaw/extensions/emotiond/)
- [x] 工具: emotiond_world_event
- [x] 工具: emotiond_get_decision

### 4. 主链验证
- [x] 手动测试 POST /event 成功
- [x] 返回完整的 emotiond 响应 (valence, arousal, appraisal, self_report)

## 待完成

### Gate A: Contract
- [ ] 确认 schema 与实际 API 完全一致
- [ ] 添加 version negotiation 机制
- [ ] 完善错误处理契约

### Gate B: E2E
- [ ] 场景 1: 普通聊天 - 用户发消息 → emotiond 处理 → 返回 response_tendency
- [ ] 场景 2: 跨轮记忆 - 第一轮输入事实 → 第二轮追问 → memory_update 生效
- [ ] 场景 3: 任务结果回流 - 工具执行 → external_result 回流

### Gate C: Preflight
- [ ] artifact 落盘机制
- [ ] 边界检查: EgoCore 不私自实现主体本体
- [ ] 边界检查: OpenEmotion 不直接执行工具

## v6k 观察期状态

| Day | Date | Verdict | Notes |
|-----|------|---------|-------|
| 1 | 2026-03-17 | BOOTSTRAP | 无真实流量通过 whitelist 场景 |

**原因**: 真实入口未闭环，whitelist 场景未被触发。

**下一步**: 
1. 让 OpenClaw agent 通过 EgoCore adapter 调用 emotiond
2. 确保真实用户请求触发 whitelist 场景
3. 开始有效观察天数累计

## 文件位置

```
EgoCore:
- contracts/event_input.schema.json
- contracts/openemotion_output.schema.json
- egocore/adapters/openemotion_adapter.py

OpenEmotion:
- emotiond/api.py (/event 端点)
- emotiond/models.py (Event schema)
- emotiond/core.py (process_event)

OpenClaw:
- ~/.openclaw/extensions/emotiond/index.ts

Systemd:
- ~/.config/systemd/user/emotiond.service
```

## 架构边界

```
用户消息 → OpenClaw (CEO agent)
         ↓
    EgoCore Adapter
         ↓
    emotiond /event
         ↓
    process_event() → identity/memory/appraisal update
         ↓
    response_tendency → EgoCore 决策
         ↓
    回复用户 / 执行任务 / 等待
```

**原则**:
- EgoCore: 宿主、运行时、执行、审计、最终裁决
- OpenEmotion: identity/self-model/memory/appraisal/reflection 本体
- 禁止 EgoCore 私自实现主体本体逻辑
- 禁止 OpenEmotion 直接执行工具
