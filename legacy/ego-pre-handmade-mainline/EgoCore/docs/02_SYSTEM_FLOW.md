# 02_SYSTEM_FLOW.md

## 总体正式主链

```text
用户/环境事件
  → EgoCore 入口层 (Telegram / CLI / API)
  → EgoCore runtime / session / task orchestration
  → EgoCore OpenEmotion adapter / contract guard
  → OpenEmotion (identity / self-model / memory / appraisal / reflection)
  → EgoCore runtime decision / tool / safety / delivery
  → 外部动作 / 回复 / 状态更新
  → 结果回流 OpenEmotion
```

## 文字版流程

### 1. 外部事件进入 EgoCore
入口目前主要由 EgoCore 承担：
- `app/telegram_bot.py`
- `app/cli.py`
- `app/main.py`
- `app/command_router.py`

### 2. EgoCore 进行运行时编排
EgoCore 管理：
- session lifecycle
- task lifecycle
- tool execution
- safety/approval
- outward response contract

当前 Telegram Runtime v2 主链主要落在：
- `app/runtime_v2/loop.py`
- `app/runtime_v2/decision_engine.py`
- `app/runtime_v2/transition.py`
- `app/runtime_v2/tool_broker.py`
- `app/runtime_v2/completion_contract.py`
- `app/runtime_v2/delivery_policy.py`
- `app/runtime_v2/telegram_bridge.py`

### 3. EgoCore 向 OpenEmotion 发送结构化事件
正式主链要求通过结构化接口联动，不靠 prompt 文本临时约定字段。
相关契约与 adapter 证据位于：
- `contracts/event_input.schema.json`
- `contracts/openemotion_output.schema.json`
- `egocore/adapters/openemotion_adapter.py`
- `docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md`

### 4. OpenEmotion 做主体内核处理
OpenEmotion 负责：
- identity continuity
- self-model
- memory evolution
- appraisal / relationship update
- reflection / policy hint

主要目录：
- `openemotion/`
- `emotiond/`

### 5. EgoCore 做最终现实裁决
OpenEmotion 给出主体侧输出后：
- 是否真的回复
- 是否开任务
- 是否调用工具
- 是否 block / escalate / wait
- 如何外发

这些最后仍归 EgoCore。

### 6. 结果回流
如果工具执行、外发、任务推进产生真实结果，应该：
- 记入 audit / trace / artifacts
- 必要时回流 OpenEmotion 作为 external_result / downstream event

## 运行时失败回流与证据链

### 失败不等于完成
必须区分：
- plan 生成
- act 执行
- verifier 通过
- external effect 生效

### 证据链
在 EgoCore 侧优先看：
- `logs/`
- `artifacts/`
- Telegram Runtime v2 trace (`runtime_v2.turn.*`)
- tests 与 replay 工具

## 常见场景流程样例

### 场景 A：Telegram 文件修改请求
1. 用户在 Telegram 发修改请求
2. `app/telegram_bot.py` 接入
3. `app/runtime_v2/telegram_bridge.py` 做 ingress/pre-runtime/delivery planning
4. `app/runtime_v2/loop.py` 驱动 LLM action protocol
5. `app/runtime_v2/tool_broker.py` 执行 file/shell
6. `app/runtime_v2/completion_contract.py` 验证效果
7. EgoCore 外发完成回复

### 场景 B：用户追问“你没改啊”
1. Telegram 入口进入
2. bridge 检测为 challenge turn
3. 继续当前 Runtime v2 上下文，不丢任务
4. 走 progress / challenge follow-up 语义，而不是机械 busy 占位

### 场景 C：主体相关更新
1. EgoCore 结构化事件
2. adapter 调 emotiond/OpenEmotion
3. OpenEmotion 产出 identity/self_model/memory/appraisal/reflection 语义更新
4. EgoCore 结合现实边界做最终外部裁决
