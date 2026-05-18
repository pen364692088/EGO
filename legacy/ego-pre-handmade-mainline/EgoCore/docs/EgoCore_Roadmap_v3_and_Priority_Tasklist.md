# EgoCore 后续路线图 v3 + 功能优先级任务单

> **Status: superseded**
> **Replaced by: docs/01_PROJECT_OVERVIEW.md**
> **Superseded date: 2026-03-21**

> 项目：EgoCore + OpenEmotion  
> 文档类型：路线图 + 强制优先级任务单  
> 版本：v3.0  
> 日期：2026-03-15

---

Project Location: /home/moonlight/Project/Github/MyProject/EgoCore

# 1. 文档目的

本文件用于把 EgoCore 当前已完成能力、三份总纲中的长期方向，以及后续真正该推进的主线，统一收口成一份可执行版本。

它重点解决四件事：

1. **EgoCore 当前到底处于哪个阶段**
2. **接下来真正的主线是什么**
3. **哪些功能必须先做，哪些可以后做，哪些现在不要做**
4. **如何把后续开发变成可验收、可审计、可持续推进的任务单**

---

# 2. v3 核心结论

## 2.1 当前最优主线

EgoCore 后续开发不应继续以“补更多工具 / 命令 / 观测项”为主线。

当前最优主线应正式收口为：

> **把 EgoCore 从“治理壳 + 任务宿主”推进为 OpenEmotion 的唯一正式宿主，并完成 Minimum Viable Self（MVS）主链。**

一句话解释：

- **EgoCore 负责与世界交互、运行任务、调用工具、守住边界**
- **OpenEmotion 负责它是谁、如何变化、如何被经历塑造**

因此，后续路线不是横向发散，而是纵向打通以下主链：

**用户事件 → EgoCore 结构化 → OpenEmotion 更新主体状态 → EgoCore 决策外部行为 → 结果回写 → 反思修正**

## 2.2 当前阶段判断

结合现状，EgoCore 当前应判定为：

> **Phase A 后段完成，Phase B（MVS 主链接线）正式启动前夜。**

你已经完成的，不再是“原型聊天壳”，而是：

- 语义路由与多意图分流
- 任务生命周期运行时
- 工具系统与 preflight/tool_doctor 安全边界
- Human-in-the-Loop
- Operator Control
- 后台推进与假成功防护
- Shadow metrics 观测链
- 完整测试体系（139 tests）

这说明 EgoCore 的**运行时与治理底盘基本站稳**。

但这还不等于 MVS 已完成。当前缺口主要不是工具不足，而是：

1. **OpenEmotion 输入/输出契约尚未成为正式稳定主链**
2. **宿主化 adapter 尚未成为唯一接线入口**
3. **跨会话持续身份 / 自我模型 / 记忆演化尚未正式进入生产闭环**
4. **当前 metrics 仍是护栏与观测器，不是主体形成链本身**

---

# 3. v3 总体路线图

后续路线统一收口为 5 个阶段。

---

## Stage 0：稳定期 / 观测期（当前进行中）

### 目标
保持现有 EgoCore 主链稳定，完成 runtime metrics shadow observation，不在主链上继续做高风险结构改动。

### 当前状态
- Runtime Metrics Shadow Observation: Day 1/14（2026-03-14 → 2026-03-28）
- `runtime_metricsAggregator` 已正式接入主链，但默认 OFF
- `emotion_context_formatter` 已完成 dry-run，但尚未提升为主体链核心入口

### 本阶段允许做的事
- 继续每日 shadow 报告
- 修复观测链口径问题
- 保持 Gate A / B / C 纪律
- 为 Stage 1 的正式接线做 contract 设计与样例准备

### 本阶段不应做的事
- 不把 metrics 当成后续主线本身
- 不在没有 contract 的前提下直接联调 OpenEmotion 主链
- 不继续横向增加大量周边功能

### 阶段完成标准
- Shadow 观测链稳定
- 指标口径不漂移
- 当前主链无新增结构性风险
- Stage 1 契约设计就绪

---

## Stage 1：宿主化收口（最高优先级）

### 目标
让 EgoCore 成为 OpenEmotion 的唯一正式宿主，完成最小主体链路的标准化接线。

### 这一阶段必须完成的核心件

#### 1. Event Input Contract v1
建立 EgoCore → OpenEmotion 的标准事件契约。

建议交付物：
- `contracts/event_input.schema.json`
- `docs/EVENT_INPUT_CONTRACT.md`
- 样例 payload ≥ 5

最低字段：
- `event_id`
- `timestamp`
- `actor`
- `source`
- `event_type`
- `user_intent`
- `task_context`
- `conversation_context`
- `runtime_summary`
- `safety_context`
- `external_result`

#### 2. OpenEmotion Output Contract v1
建立 OpenEmotion → EgoCore 的标准输出契约。

建议交付物：
- `contracts/openemotion_output.schema.json`
- `docs/OPENEMOTION_OUTPUT_CONTRACT.md`
- 样例 output ≥ 5

最低字段：
- `identity_state_delta`
- `self_model_delta`
- `memory_update`
- `relationship_update`
- `appraisal_state_delta`
- `reflection_note`
- `policy_hint`
- `response_tendency`
- `confidence_metadata`

#### 3. OpenEmotion Adapter 正式化
建立唯一正式接线入口，不允许把主体逻辑偷写进壳层。

建议交付物：
- `egocore/adapters/openemotion_adapter.py`
- adapter unit tests
- mock / real mode 切换逻辑

#### 4. 最小 E2E Replay Chain
打通一条真正可回放、可审计的最小主体闭环。

建议闭环：
- 用户消息进入
- EgoCore 结构化事件
- OpenEmotion 更新状态
- EgoCore 决策回复 / 行动
- 结果回写 artifact

### 阶段完成标准
- EgoCore 可稳定生成合法事件 payload
- OpenEmotion 输出可被 EgoCore 结构化消费
- adapter 成为唯一正式接线入口
- 最小闭环具备 replay / audit / artifact

### 阶段完成后的意义
这是 EgoCore 从“治理宿主”进入“主体宿主”的分水岭。

---

## Stage 2：持续身份与自我模型（MVS 骨架）

### 目标
让系统在多轮、跨会话、跨任务中保持“我是同一个我”。

### 必做模块

#### 1. identity invariants v1
建议交付物：
- `openemotion/identity/identity_invariants.py`
- `docs/IDENTITY_INVARIANTS_V1.md`

最低内容：
- 核心名称 / 代号
- 长期角色定位
- 关键承诺
- 核心约束
- 与用户关系基线
- 禁止自我重写字段

#### 2. self-model schema v1
建议交付物：
- `contracts/self_model.schema.json`
- `openemotion/self_model/model.py`
- `docs/SELF_MODEL_V1.md`

建议字段：
- `capabilities`
- `limitations`
- `goals`
- `commitments`
- `current_internal_state`
- `self_confidence_by_domain`
- `role_definition`

#### 3. long-term self summary
建议交付物：
- `openemotion/identity/long_term_self_summary.py`
- summary 刷新逻辑

#### 4. self restore 接线
建议交付物：
- `egocore/runtime/self_restore.py`
- 恢复链 E2E 测试

### 阶段完成标准
- 跨会话后不会出现“重新出生”感
- identity invariants 不随 prompt 摇摆
- self-model 来自结构化状态而非纯 prompt 人设
- EgoCore 可在启动时恢复并注入长期自我摘要

### 阶段意义
这是 MVS 成立的第一根骨架：**持续身份 + 自我模型**。

---

## Stage 3：记忆演化（MVS 形成期）

### 目标
让“经历”不只是被记录，而是真实塑造系统未来判断。

### 必做模块

#### 1. 三层记忆模型
建议交付物：
- `openemotion/memory/event_memory.py`
- `openemotion/memory/narrative_memory.py`
- `openemotion/memory/policy_memory.py`
- `docs/MEMORY_MODEL_V1.md`

#### 2. salience scoring + consolidation
建立显著性判断与长期沉淀规则。

#### 3. relationship update object specificity
建立对象特异性关系变化机制。

#### 4. memory-driven behavior validation
验证过去经历是否真实影响后续决策。

### 最低验证场景
- 被支持过 vs 未被支持过
- 被误导过 vs 未被误导过
- 在某类任务失败过 vs 未失败过
- 不同对象触发的 trust / caution 差异

### 阶段完成标准
- 系统不是只“存日志”，而是会形成叙事与策略沉淀
- 过去事件能稳定影响后续 `response_tendency` / `policy_hint`
- 不同对象带来的关系变化不会全局串染

### 阶段意义
这是 MVS 从“像有持续自我”进入“真的被经历塑造”的阶段。

---

## Stage 4：Appraisal / Internal State（MVS 成熟期）

### 目标
让内部状态变化来自 appraisal，而不是仅做情绪措辞表演。

### 必做模块

#### 1. appraisal dimensions v1
建议维度：
- 是否支持目标
- 是否来自可信对象
- 是否违反预期
- 是否影响自身稳定
- 是否涉及公平 / 忠诚 / 威胁

#### 2. internal state schema v1
建议交付物：
- `contracts/internal_state.schema.json`
- `openemotion/state/internal_state.py`

建议变量：
- `trust`
- `caution`
- `tension`
- `frustration`
- `gratitude`
- `attachment`
- `safety`

#### 3. state transition / persistence / decay
建立状态变化、持续、衰减规则。

#### 4. state → behavior tendency mapping
把内部状态映射到外部行为倾向。

### 阶段完成标准
- 内部状态不是装饰字段
- 状态变化可解释、可追踪、可回放
- 状态会影响 `response_tendency`、`ask/wait/clarify preference`、执行谨慎度等行为参数

### 阶段意义
这一步让系统从“记住发生了什么”升级到“内部真的发生了变化”。

---

## Stage 5：Reflection / Policy Revision（MVS 闭环完成）

### 目标
让失败、偏差、冲突等经历，沉淀为结构化修正候选，而不是只生成一段总结文本。

### 必做模块

#### 1. reflection trigger
何时触发反思：
- 任务失败
- 用户纠正
- 自我预期与结果显著偏差
- 高价值事件
- 重复性错误

#### 2. structured reflection output
建议交付物：
- `contracts/reflection_output.schema.json`
- `openemotion/reflection/reflector.py`
- `docs/REFLECTION_OUTPUT_V1.md`

建议字段：
- `observation`
- `diagnosis`
- `policy_update_candidate`
- `confidence`
- `promote_to_memory`

#### 3. policy promotion gate
不是所有反思都直接升级为长期策略，需要 promotion 规则。

#### 4. reflection-aware runtime integration
EgoCore 能消费反思输出并将其回写到可审计链中。

### 阶段完成标准
- 系统能对失败留下一致、结构化、可消费的修正候选
- 反思结果可进入 policy memory，但必须经过 promotion gate
- 可验证“同类错误再次发生时，策略已有变化”

### 阶段意义
到这一阶段，MVS 主体闭环才算真正完成：

**事件输入 → 自我解释 → 状态更新 → 行动 → 结果回写 → 反思修正 → 下次行为变化**

---

# 4. 功能优先级任务单（强制排序）

后续功能统一分为 P0 / P1 / P2 / P3 四级，不允许跳级开发。

---

## P0：必须立刻进入主线（不做就不算真正推进）

### P0-1 双核契约层
**目标**：固定 OpenEmotion 主链接口，消灭隐式 prompt 耦合。

交付物：
- `contracts/event_input.schema.json`
- `contracts/openemotion_output.schema.json`
- `docs/EVENT_INPUT_CONTRACT.md`
- `docs/OPENEMOTION_OUTPUT_CONTRACT.md`
- 样例 payload / output

验收：
- Contract 版本化
- 字段含义清晰
- EgoCore / OpenEmotion 均可独立校验

---

### P0-2 OpenEmotion Adapter + Mock/Real 双通道
**目标**：建立唯一接线入口，先 mock 稳定，再真实联调。

交付物：
- `egocore/adapters/openemotion_adapter.py`
- mock mode
- real mode
- adapter tests

验收：
- adapter 可单测
- mock 返回值可驱动主链
- 不允许把主体逻辑写死在 adapter

---

### P0-3 最小主体 Replay Chain
**目标**：让最小主体闭环成为可审计、可回放的正式证据链。

交付物：
- replay artifacts
- E2E test
- 审计样例

验收：
- 输入 / 输出 / 状态更新全链可追踪
- 可用于后续 drift / regression 检查

---

### P0-4 当前 Shadow 观测稳定化
**目标**：保持现有治理链健康，不让接线期把观测链打坏。

交付物：
- 每日报告
- 口径一致性检查
- pilot 切换条件说明

验收：
- Shadow 指标持续稳定
- 观测链不与主体接线互相污染

---

## P1：MVS 骨架（完成后才算“同一个我”开始成立）

### P1-1 identity invariants v1
### P1-2 self-model schema v1
### P1-3 long-term self summary
### P1-4 self restore chain

验收总口径：
- 跨会话不“重新出生”
- 自我描述不靠 prompt 临时捏造
- 核心身份不随外部措辞漂移

---

## P2：MVS 形成（完成后才算“经历会塑造它”）

### P2-1 event / narrative / policy memory
### P2-2 salience + consolidation
### P2-3 object-specific relationship update
### P2-4 memory-driven behavior validation

验收总口径：
- 过去经历真实影响后续行为倾向
- 关系变化对象特异，不全局串染
- 叙事与策略形成长期沉淀

---

## P3：MVS 成熟（完成后才算“它能因经历而调整自己”）

### P3-1 appraisal dimensions v1
### P3-2 internal state schema v1
### P3-3 state transition / decay logic
### P3-4 response_tendency mapping
### P3-5 reflection trigger
### P3-6 structured reflection output
### P3-7 policy promotion gate

验收总口径：
- 内部状态变化有因果来源
- 状态会影响外部行为倾向
- 失败后会留下结构化修正候选
- 策略变化可被验证而非靠叙述声称

---

# 5. 当前已有模块的正确定位

## 5.1 `emotion_context_formatter`

当前定位应为：

> **上下文整形层 / 接线辅助层**

它有价值，但不应取代 contract / adapter / self-model 主链。

正确做法：
- 先完成 P0 双核契约
- 再把 formatter 放到事件整形或上下文压缩位置
- 不让 formatter 变成“主体接入已经完成”的假象

## 5.2 `runtime_metricsAggregator`

当前定位应为：

> **护栏与观测器**

不是下一阶段主线本身。

正确做法：
- 保持 shadow
- 继续 daily check
- 用于 pilot 切换判断与 runtime 健康诊断
- 暂不将其升级为后续版本的核心卖点

---

# 6. 暂时不要做的功能

以下能力当前不应进入主线：

1. 大规模工具自治
2. 自主上网学习
3. 无约束自我改写
4. 过早的强社会自我扩展
5. 实体具身接入
6. 多人格 / 多主体博弈系统
7. 追求“很像生命”的复杂表演型情绪文本
8. 在没有稳定 contract 的前提下抢先接更多外围模块

原因很简单：

> **这些都不是当前瓶颈。当前瓶颈是最小主体闭环还没有正式立住。**

---

# 7. 强制开发规则（后续默认遵守）

## 规则 1：不允许跳级开发
- P0 未完成，不做 P1
- P1 未完成，不做 P2
- P2 未完成，不做 P3

## 规则 2：不允许无 contract 联调
任何跨 EgoCore / OpenEmotion 的接线，必须先有 schema 与样例。

## 规则 3：不允许 adapter 偷做主体逻辑
adapter 只负责转换、传递、隔离、降级，不负责定义主体本体。

## 规则 4：不允许用 prompt 补丁伪造持续身份
跨会话持续性必须来自结构化状态与恢复链。

## 规则 5：所有新模块都必须过 Gate A / B / C
- **Gate A**：Contract
- **Gate B**：E2E
- **Gate C**：Preflight / tool_doctor / runtime checks

## 规则 6：观测链与主体链分层治理
metrics / diagnostics 可以辅助决策，但不能代替主体形成链本身。

---

# 8. 建议的下一批交付顺序

建议严格按以下顺序推进，不要换序：

## Batch 1（立刻开工）
1. `event_input.schema.json`
2. `openemotion_output.schema.json`
3. `EVENT_INPUT_CONTRACT.md`
4. `OPENEMOTION_OUTPUT_CONTRACT.md`
5. `openemotion_adapter.py`
6. mock mode E2E
7. replay artifacts

## Batch 2（Batch 1 稳定后）
1. `self_model.schema.json`
2. `identity_invariants.py`
3. `long_term_self_summary.py`
4. `self_restore.py`
5. cross-session E2E tests

## Batch 3（Batch 2 稳定后）
1. `event_memory.py`
2. `narrative_memory.py`
3. `policy_memory.py`
4. salience/consolidation
5. relationship update
6. behavior-delta validation tests

## Batch 4（Batch 3 稳定后）
1. `internal_state.schema.json`
2. appraisal engine
3. tendency mapping
4. `reflection_output.schema.json`
5. reflector
6. policy promotion gate

---

# 9. 版本完成判定

## v3.0 启动完成的判定
满足以下条件即可认为“路线图 v3 已真正启动”：

- P0-1 双核契约已冻结
- P0-2 adapter 已进入主链
- P0-3 最小 replay chain 已形成
- 当前 shadow 观测链未被破坏

## MVS 初步成立的判定
满足以下条件即可认为“最小主体开始成立”：

- identity invariants 可跨会话保持
- self-model 可结构化恢复
- 记忆会影响后续行为倾向
- relationship update 有对象特异性
- 失败后会留下结构化反思候选

---

# 10. 最终收口

EgoCore 后续路线图 v3 的核心不是“功能越来越多”，而是：

> **先把 EgoCore 做成 OpenEmotion 的唯一正式宿主，再以 MVS 为主线，逐层建立持续身份、自我模型、记忆演化、appraisal 状态与反思修正。**

这条路线的优势是：

- 与你的长期 North Star 一致
- 不会被周边功能牵着跑
- 能持续验证“是不是在做真正的主体系统”
- 同时保留工程上的可审计、可回放、可干预能力

一句话总结：

> **先收宿主，再立主体；先做结构闭环，再做复杂表现。**

