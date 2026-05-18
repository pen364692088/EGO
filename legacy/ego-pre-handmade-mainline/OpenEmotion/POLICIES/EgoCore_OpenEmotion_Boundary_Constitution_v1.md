# EgoCore × OpenEmotion 边界宪章 v1

> 文档类型：正式边界与功能分层强制规范  
> 适用范围：EgoCore + OpenEmotion 后续全部设计、开发、迁移、联调、验收  
> 目标：彻底收口边界、规范功能划分、禁止双主和长期越界实现

OpenEmotion仓库地址:/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
EgoCore仓库地址:/home/moonlight/Project/Github/MyProject/EgoCore
---

# 0. 先给结论

本系统只有两个正式核心：

- **EgoCore：对外宿主 / 运行时 / 执行层 / 治理壳**
- **OpenEmotion：主体内核 / self-model / memory / appraisal / reflection 本体**

从本规范生效起，以下规则作为硬前提执行：

1. **Self-Model、Identity、Long-Term Self Summary、Memory、Appraisal、Reflection 的正式本体统一归 OpenEmotion。**
2. **EgoCore 只允许承接、标准化、调用、注入、缓存、镜像、审计，不允许长期拥有这些主体数据的最终解释权。**
3. **任何能力只能有一个权威源。允许镜像，不允许双主。**
4. **临时 shim 允许，但必须登记、限期、可迁回；未登记 shim 视为违规实现。**
5. **任何新功能在开写前，必须先完成边界判定，不允许“先写再说”。**

---

# 1. 系统正式定位

## 1.1 EgoCore 的正式定位

EgoCore 不是单纯 UI，也不是薄壳。它是整个系统的：

- 用户交互前端
- 会话运行时
- 任务运行时
- 工具执行层
- 外部连接器层
- 安全边界层
- replay / trace / audit 治理壳
- OpenEmotion 的唯一正式宿主

一句话：

> **EgoCore 决定系统如何与世界交互、如何执行、如何守住现实边界。**

## 1.2 OpenEmotion 的正式定位

OpenEmotion 不是插件，不是风格层，不是“补充模块”。它是整个系统的主体内核，负责：

- identity continuity
- self-model
- long-term self summary
- memory evolution
- appraisal / internal state
- reflection / structured revision
- developmental self 的后续演进能力

一句话：

> **OpenEmotion 决定系统是谁、如何被经历塑造、如何理解并修正自己。**

---

# 2. 权威源总表（硬规则）

## 2.1 EgoCore 权威数据

以下数据的最终解释权只在 EgoCore：

- 用户消息入口与渠道状态
- session lifecycle
- task lifecycle
- tool execution state
- runtime orchestration state
- safety / approval / block state
- outward response contract
- replay / audit / trace artifact
- ask / wait / resume / escalate 等对外流程控制状态

## 2.2 OpenEmotion 权威数据

以下数据的最终解释权只在 OpenEmotion：

- identity invariants
- self-model structure
- long-term self summary
- event / narrative / policy memory
- appraisal state
- relationship update semantics
- reflection result
- policy update candidate semantics

## 2.3 镜像规则

允许：

- EgoCore 缓存 OpenEmotion 的主体摘要用于运行时加速
- EgoCore 保存最近一次 self-model 快照用于 restore 注入
- OpenEmotion 读取 EgoCore 的任务结果作为事件输入

禁止：

- EgoCore 将缓存当作主体真相源
- OpenEmotion 将事件副本当作运行时真相源
- 两边长期各维护一套同类核心状态并各自解释

**判断标准：谁能最终定义字段语义，谁就是权威源。只能有一个。**

---

# 3. 功能归属总表（以后按这个判）

## 3.1 必属 EgoCore 的功能

### A. 用户与渠道
- Telegram / Web / CLI / API 等接入
- 用户消息入口
- session 开启、关闭、恢复、超时
- 多轮对话编排
- ask / wait / resume / continue 控制

### B. 运行时与任务编排
- task runtime
- step orchestration
- pause / retry / cancel / resume
- 前后台任务协调
- 执行状态持久化
- runtime 恢复

### C. 工具与执行
- file / shell / python / diagnostics / preflight / tool_doctor
- 工具权限控制
- 高风险动作阻断
- 工具结果结构化回写

### D. 治理与证据链
- replay
- audit trail
- trace
- hard gate
- test harness
- determinism / freeze
- artifact discipline

### E. 对外表达与现实裁决
- response plan
- outward response contract
- certainty / commitment / tone 边界
- 最终是否回复 / 是否触发任务 / 是否执行工具 / 是否 block / 是否 escalate

### F. OpenEmotion 宿主承接
- 事件标准化
- adapter
- compatibility guard
- restore injection
- host-side cache / mirror
- 将 OpenEmotion 输出与运行时、安全边界、工具权限综合后做现实裁决

## 3.2 必属 OpenEmotion 的功能

### A. 持续身份
- identity invariants
- identity boundary semantics
- relationship baseline semantics
- long-term self summary
- narrative identity anchors

### B. 自我模型
- capability model
- limitation model
- role / commitment model
- goal hierarchy
- self-confidence by domain
- current internal state semantics
- self-description semantics

### C. 记忆演化
- event memory
- narrative memory
- policy memory
- salience scoring
- consolidation
- memory-driven change

### D. appraisal / 内部状态
- appraisal dimensions
- trust / caution / tension / frustration / gratitude / attachment / safety 等状态变量
- object-specific transition
- persistence / decay rules

### E. 反思与修正
- reflection trigger semantics
- diagnosis
- structured revision
- policy update candidate generation
- promote-to-memory suggestions

### F. 长期发展能力
- developmental core
- endogenous drives
- self-maintenance semantics
- reflective self / counterfactual self

---

# 4. 明确禁止的越界行为

## 4.1 EgoCore 严禁偷做

EgoCore 严禁私自定义、重写或长期承载以下本体逻辑：

- 深层 self-model 本体
- 长期 identity invariants 本体
- long-term self summary 本体生成规则
- 记忆演化逻辑
- appraisal / emotion state 本体
- reflection 结论本体
- 长期叙事身份演化逻辑

EgoCore 允许：

- mirror
- cache
- loader
- injector
- validator
- compatibility guard
- host-side snapshot
- restore audit

但这些都必须明确标注为：

> **host-side mirror / cache / injector，不是主体本体。**

## 4.2 OpenEmotion 严禁偷做

OpenEmotion 严禁直接承担以下现实层职责：

- 渠道接入
- 会话总控
- 任务编排
- 工具执行
- 工具权限审批
- 高风险动作直接落地
- 对外输出前硬边界治理
- 运维调度

OpenEmotion 允许：

- 提供建议
- 提供倾向
- 提供风险解释
- 提供 response_tendency / policy_hint / reflection candidate

但不能越过 EgoCore 直接执行现实动作。

---

# 5. 接口边界（强制）

## 5.1 EgoCore → OpenEmotion

输入必须是**结构化事件**，不是拼 prompt。

最小输入对象必须围绕以下字段族：

- event_id
- timestamp
- actor
- source
- event_type
- user_intent
- conversation_context
- task_context
- runtime_summary
- safety_context
- external_result

规则：

1. schema 先行
2. 版本化
3. 兼容性策略明确
4. 有样例 payload
5. 有 replay regression

## 5.2 OpenEmotion → EgoCore

输出必须是**结构化结果**，不是只回一段自然语言。

最小输出对象必须围绕以下字段族：

- identity_state_delta
- self_model_delta
- memory_update
- relationship_update
- appraisal_state_delta
- reflection_note
- policy_hint
- response_tendency
- confidence / stability metadata

规则：

1. 自由文本只能作为解释层
2. 程序消费必须依赖结构字段
3. 任意新增字段必须先改 schema，再联调

## 5.3 禁止接口漂移

以下行为一律违规：

- 临时靠 prompt 文本约定字段
- 未版本化的接口随意加删
- 两边各自维护一套不同 schema
- 在未定义契约前先联调

---

# 6. 仓库与模块正式落位

## 6.1 EgoCore 仓库应长期包含

- app /
- interaction runtime /
- task runtime /
- tool runtime /
- safety / preflight /
- governance / replay / audit /
- connectors /
- response contract /
- openemotion adapter /
- restore injector /
- host-side cache / mirror /

## 6.2 OpenEmotion 仓库应长期包含

- identity /
- self_model /
- memory /
- appraisal /
- reflection /
- narrative /
- policy /
- developmental_core /
- internal state contracts /

## 6.3 特别规定：P1 相关功能的正式归属

以后统一按下面认定：

### 正式属于 OpenEmotion
- identity invariants
- self-model
- long-term self summary
- summary refresh logic
- self-model update semantics

### 正式属于 EgoCore
- self restore orchestration
- context injection
- compatibility checks
- host-side summary loading
- restore audit artifacts

### 过渡态允许但必须整改的情况
如果当前仓库里已经出现以下实现位于 EgoCore：

- self-model 本体逻辑
- identity 本体逻辑
- long-term self summary 本体生成逻辑

则必须统一定性为：

> **过渡期 shim / mirror / host-side loader**

并补齐以下 3 项：

1. `SHIM_REGISTER.md`
2. 迁回 OpenEmotion 的目标版本
3. 迁移完成后的删除计划

否则视为长期仓库污染。

---

# 7. 新功能归属判定规则（以后每次都先判）

任何新功能在开写前，必须先经过以下判断：

## 7.1 一步判定法

如果这个功能主要回答：

- “系统如何与外界交互 / 执行 / 审批 / 阻断 / 编排？”
  - **归 EgoCore**

- “系统是谁 / 如何变化 / 如何被经历塑造 / 如何理解和修正自己？”
  - **归 OpenEmotion**

## 7.2 六问门禁（不答完不许开写）

1. 这个能力属于 EgoCore 还是 OpenEmotion
2. 它的权威数据归谁
3. 它和现有哪个模块耦合
4. 是否会引入双重真相源
5. 是否会让临时 shim 变成长期黑箱
6. 它失败时谁负责兜底

任何一问答不清楚，**禁止开写**。

## 7.3 冲突优先级

当归属争议出现时，按下面优先级判断：

1. **权威数据归属**
2. **最终解释权归属**
3. **失败兜底责任归属**
4. **现实动作裁决权归属**

只要一个模块既想拿解释权又不承担失败兜底，说明设计有问题。

---

# 8. Shim / Mirror / Cache 正式管理规则

## 8.1 允许的过渡实现

允许短期存在以下类型：

- shim
- mirror
- cache
- injector-side adapter helper

## 8.2 允许前提

必须同时满足：

1. 只是为了联调或迁移过渡
2. 不拥有最终解释权
3. 有明确生命周期
4. 有迁回正式边界的计划
5. 有独立登记文件

## 8.3 必须登记的信息

每个 shim 必须记录：

- 名称
- 所在仓库与路径
- 为什么存在
- 替代正式归属在哪
- 到哪个版本前必须迁移
- 若不迁移会造成什么风险
- 迁移完成后删除谁

## 8.4 一票否决条件

只要出现以下任一情况，该 shim 立即视为违规：

- 开始承载最终解释权
- 没有到期版本
- 没有删除计划
- 被多个新功能继续复用扩张
- 变成默认长期实现

---

# 9. 决策权边界

## 9.1 EgoCore 保留的最终裁决权

在现实动作层面，EgoCore 保留最终裁决权：

- 是否回复
- 是否发起任务
- 是否执行工具
- 是否阻断
- 是否 ask / wait / escalate

## 9.2 OpenEmotion 保留的主体解释权

在主体层面，OpenEmotion 保留：

- 当前主体状态为何如此的解释权
- 某次经历是否影响长期叙事的建议权
- 关系为何发生变化的解释权
- 策略修正候选的生成权

## 9.3 高风险动作硬规则

高风险动作永远不得由 OpenEmotion 直接执行。

流程固定为：

1. OpenEmotion 给出倾向 / 风险 / 内在判断
2. EgoCore 结合运行时、安全边界、工具权限做现实裁决
3. 执行结果作为事件再回流 OpenEmotion

---

# 10. 后续功能的正式分层表

## L0：世界接口层（EgoCore）

- connectors
- user input
- channel handling
- outward response formatting

## L1：运行时与执行层（EgoCore）

- session runtime
- task runtime
- tools
- orchestration
- approval / block / retry / pause / resume

## L2：治理与证据层（EgoCore）

- replay
- audit
- trace
- gate
- tool_doctor
- preflight

## L3：边界适配层（EgoCore → OpenEmotion）

- event normalization
- adapter
- schema compatibility guard
- restore injection
- host-side cache / mirror

## L4：主体骨架层（OpenEmotion）

- identity invariants
- self-model
- long-term self summary

## L5：主体演化层（OpenEmotion）

- event / narrative / policy memory
- salience / consolidation
- relationship evolution

## L6：主体状态层（OpenEmotion）

- appraisal
- internal state
- state decay / persistence
- state-to-tendency mapping

## L7：主体修正层（OpenEmotion）

- reflection
- diagnosis
- policy update candidate
- promotion

规则：

- L0–L3 归 EgoCore
- L4–L7 归 OpenEmotion
- 禁止跨层偷做

---

# 11. 当前应立即执行的整改

## 11.1 对已有 P1 实现的重新定性

如果当前 P1-A / P1-B / P1-C1 中的以下实现位于 EgoCore 仓库：

- identity invariants schema / logic
- self-model schema / logic
- long-term self summary generator / logic

则统一先按以下方式处理：

### 可保留在 EgoCore 的部分
- schema mirror
- loader
- validator
- compatibility guard
- restore injector side helper
- restore audit

### 必须迁回 OpenEmotion 的部分
- 本体字段语义定义
- 更新规则
- 生成逻辑
- 内在解释逻辑
- 变更语义

## 11.2 迁移原则

迁移顺序必须是：

1. 先把 OpenEmotion 端正式模块建起来
2. 再让 EgoCore 改为读取 OpenEmotion 产物
3. 再删除 EgoCore 端本体逻辑
4. 最后保留最薄的 host-side mirror / injector

严禁反过来：

- 一边继续在 EgoCore 扩写本体
- 一边口头说“以后会迁”

## 11.3 WS-C 起的硬限制

从 WS-C / C1 开始，以下主体逻辑禁止再写入 EgoCore：

- memory model
- salience
- consolidation
- relationship semantics
- appraisal state
- reflection output semantics

否则视为架构回退。

---

# 12. 开发前检查清单（强制）

每个新任务开始前，必须先写出以下小节：

## A. Capability Ownership
- 归 EgoCore / OpenEmotion？

## B. Authority Source
- 权威数据在哪？

## C. Mirror Need
- 是否需要 cache / mirror / shim？

## D. Boundary Risk
- 是否有双主风险？

## E. Failure Owner
- 失败由谁兜底？

## F. Exit Plan
- 如果有临时 shim，何时删除？

没有这 6 节的任务单，不允许进入开发。

---

# 13. Gate 规则（以后统一）

## Gate A：Boundary Contract
必须证明：

- 模块归属明确
- schema 明确
- 权威源明确
- 不存在明显双主

## Gate B：Boundary E2E
必须证明：

- EgoCore 与 OpenEmotion 通过结构化接口联动
- 不是靠 prompt 补丁联动
- 越界时有明确失败出口

## Gate C：Boundary Integrity
必须证明：

- cache / mirror / shim 已登记
- replay / audit 可追踪
- 没有把过渡实现伪装成正式边界

---

# 14. 一句话准则

以后所有争议，按这句话裁决：

> **EgoCore 负责让系统安全、可控、可执行地面向世界；OpenEmotion 负责让系统在时间中成为同一个自己并被经历塑造。**

如果某个功能既不属于“面向世界的现实裁决”，也不属于“主体内在形成与演化”，说明需求本身还没定义清楚，不允许直接开写。

