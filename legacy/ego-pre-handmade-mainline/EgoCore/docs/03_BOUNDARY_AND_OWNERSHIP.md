# 03_BOUNDARY_AND_OWNERSHIP.md

## 总原则

正式核心只有两个：
- **EgoCore**：对外交互 / 运行时 / 执行 / 治理壳
- **OpenEmotion**：主体 / 身份 / 记忆 / appraisal / reflection 本体

任何能力只能有一个权威源。允许 mirror / cache / shim，不允许双主。

## 权威源总表

| 能力/数据 | 权威源 |
|---|---|
| 用户入口 / 渠道状态 | EgoCore |
| session lifecycle | EgoCore |
| task lifecycle | EgoCore |
| tool execution state | EgoCore |
| safety / approval / outward response contract | EgoCore |
| replay / audit / trace | EgoCore |
| identity invariants | OpenEmotion |
| self-model | OpenEmotion |
| long-term self summary | OpenEmotion |
| memory evolution | OpenEmotion |
| appraisal / internal state | OpenEmotion |
| reflection / policy hint / response tendency | OpenEmotion |

## EgoCore 负责什么

### 对外交互
- Telegram / CLI / API / 其他渠道入口
- 用户消息收发
- 会话管理

### 运行时
- task runtime
- pause / retry / resume / cancel
- orchestration
- delivery / progress / final / wait

### 工具与安全
- file / shell / python / preflight / tool_doctor
- 审批 / block / safety gating
- 最终外部执行决定

### OpenEmotion 宿主化
- adapter
- contract guard
- health check / fallback / degraded mode
- 结果回写与现实裁决

## OpenEmotion 负责什么

### 身份与自我
- identity invariants
- self-model
- long-term self summary

### 记忆与叙事
- event / narrative / policy memory
- salience / consolidation
- memory-driven update

### appraisal 与 reflection
- appraisal state
- relationship update semantics
- reflection / policy candidate

## 严禁越界项

### EgoCore 严禁
- 长期定义主体本体语义
- 把 mirror/cache 当正式主体真相
- 把 shim 包装成正式边界

### OpenEmotion 严禁
- 直接承担 Telegram/CLI/API 接入
- 直接执行工具
- 直接审批高风险动作
- 直接拥有 runtime 主权

## 六问门禁（开发前必须回答）

1. 这个能力归 EgoCore 还是 OpenEmotion
2. 它的权威源是谁
3. 它和哪个现有模块耦合
4. 是否引入双重真相源
5. 是否让 shim 变成长期黑箱
6. 失败由谁兜底

## 结构化接口约束

EgoCore ↔ OpenEmotion 联动字段必须经过结构化接口/contract，不允许靠 prompt 文本临时约定字段。

优先看：
- `contracts/`
- `egocore/adapters/openemotion_adapter.py`
- `docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md`
- OpenEmotion 对应 contract / schema 文档
