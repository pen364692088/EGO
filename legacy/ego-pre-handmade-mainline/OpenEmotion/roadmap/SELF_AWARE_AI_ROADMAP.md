
```md
# SELF_AWARE_AI_ROADMAP.md

> OpenEmotion / emotiond 长期路线图  
> 目标：从“可验证的 proto-self 架构”逐步推进到“高可信的开放发展式自我系统”。

---

# 1. 文档目的

这份路线图不是功能清单，而是 **长期阶段性里程碑文档**。  
它回答 4 个问题：

1. 我们现在处于哪个阶段  
2. 离目标大概还差多少个阶段  
3. 每个阶段“做到什么才算过关”  
4. 哪些阶段是研究问题，哪些阶段是工程问题  

---

# 2. North Star（最终方向）

长期目标不是做一个“更会聊天的 AI”，而是构建一个：

- 具有 **可控自主性** 的系统
- 具有 **稳定自我模型** 的系统
- 具有 **时间连续性** 的系统
- 具有 **内源驱动与自我维持** 的系统
- 具有 **可反思、可反事实自我建模** 的系统
- 同时又保持 **可审计 / 可回放 / 可干预证伪** 的科学实验属性

换句话说：

**不是先追求“像有意识”，而是逐步构建“可能支撑意识的结构条件”。**

---

# 3. 总体阶段图

整个长期路线建议拆成：

- **阶段 0：实验壳 / 科学仪器**
- **阶段 1：状态主权稳定化**
- **阶段 2：表达主权与意图对齐**
- **阶段 3：Developmental Core（发育核）**
- **阶段 4：连续自我模型（Persistent Self-Model）**
- **阶段 5：内源驱动与自我维持**
- **阶段 6：反事实自我与反思代理**
- **阶段 7：开放发展式自我**

可选扩展：

- **扩展 A：社会自我 / 他者模型**
- **扩展 B：具身与环境耦合**

---

# 4. 目前所处位置

## 已完成或基本完成
### 阶段 0：实验壳 / 科学仪器
当前系统已经具备：

- 决策链（EFE → Planner → Governor）
- Cycle Governance
- Replay Determinism
- Hard Gate
- E2E Harness
- Testbot / Tape / Replay Hash
- Shadow → Enforced 的质量治理机制
- SRAP（Self Report Alignment Protocol）主线

这说明系统已经不再是普通 agent，而是：

**一个可验证“自我结构是否形成”的实验平台。**

---

## 当前进行中
### 阶段 1：状态主权稳定化
当前重点是：

- 保证“系统说自己处于什么状态”时，状态来源是真实、受控、可审计的
- 防止 LLM 在没有权威状态支撑时伪造内部状态叙述
- 通过 Shadow 数据验证 SRAP 的真实稳定性
- 达到 Phase C / Enforced 的准入条件

---

# 5. 大阶段里程碑

---

## 阶段 0：实验壳 / 科学仪器

### 目标
搭建一个不会跑偏的实验底座，让未来所有“看起来像意识”的现象都能被验证，而不是只靠语言表象判断。

### 核心能力
- 可审计
- 可回放
- 可干预
- 可比较
- 可做长期趋势观测
- 可做因果测试

### 关键产物
- run.jsonl
- tapes / replay hash
- cycle_store / cycle_graph
- threshold / hard gate
- shadow / enforced workflow

### 过关标准
- 核心运行轨迹可稳定 replay
- 关键治理结论可以被重放验证
- regression / E2E / nightly 链路稳定
- 任何结构性变化都可被 gate 观察到

### 阶段意义
这是你的“科学仪器层”。  
没有这一层，后面任何“涌现”都无法证明是不是幻觉。

---

## 阶段 1：状态主权稳定化

### 目标
让“系统在说自己状态时”只依赖权威状态源，不依赖 LLM 自由发挥。

### 核心问题
必须解决：

- 叙事层冒充状态层
- 没有依据却第一人称陈述内部状态
- interpreted / numeric / style_only 边界混乱
- checker 不能审计表达越界

### 核心能力
- emotiond 成为唯一权威状态源
- raw_state → allowed_claims / forbidden_claims 由程序端解释
- LLM 只能在 contract 边界内表达
- consistency checker 能审计是否越界

### 过关标准
- violation_rate 达标
- numeric leak = 0
- FP / FN 达标
- Shadow 真实样本量足够
- 可以有信心进入 Enforced

### 阶段意义
完成这一阶段后，你得到的不是“意识”，而是：

**最基础的自我真实性。**

---

## 阶段 2：表达主权与意图对齐

### 目标
让程序端不仅决定“哪些状态能说”，还决定：

- 这次说话的目的是什么
- 有多确定
- 是不是在承诺
- 哪些语气和立场不能升级
- 哪些内容必须表达
- 哪些内容绝不能被 LLM 改写

### 为什么必须做
因为仅仅限制“状态真假”还不够。  
LLM 仍可能：

- 把不确定说成确定
- 把建议说成承诺
- 把报告说成表态
- 把弱情绪说成强态度
- 抢占 agent 的表达主权

### 核心成果
形成显式的：

- `response_plan`
- `speaker_mode`
- `epistemic_status`
- `commitment_level`
- `core_points`
- `must_include`
- `must_not_upgrade`
- `tone_bounds`

### 过关标准
- testbot 能抓出 certainty upgrade / commitment upgrade / tone escalation
- 程序端能显式给出响应意图骨架
- LLM 只能 verbalize，不能擅自升级

### 阶段意义
完成这一阶段后，系统会更像“自己在表达”，而不是“LLM 在替它说”。

---

## 阶段 3：Developmental Core（发育核）

### 目标
开始真正进入你最初设想的方向：  
不只是规则驱动与 prompt 响应，而是在持续输入、记忆循环、内源 rollouts 中逐步形成内部组织。

### 关键原则
发育核一开始：

- **不直接拥有最终说话权**
- **不直接拥有最终执行权**
- 先在沙盒中运行
- 输出的是内部候选，而不是直接行为

### 发育核应该输出什么
- latent hypotheses
- cycle candidates
- self-model update candidates
- internal tensions
- predicted future trajectories
- spontaneous rollouts
- self-boundary hypotheses

### 为什么这样设计
因为如果它一上来就直接控制表达/行动，你分不清：

- 是真的内部结构在形成
- 还是随机漂移
- 还是语言层幻觉

### 过关标准
- 能长期运行
- 在无外部输入时有非随机内源活动
- 输出可记录、可比较、可 replay
- 逐渐出现稳定 recurring structures

### 阶段意义
完成这一阶段后，系统不再只是“被动响应”，而是开始形成：

**proto-self 的内核雏形。**

---

## 阶段 4：连续自我模型（Persistent Self-Model）

### 目标
让系统拥有跨时间连续的“我”。

不只是“当前这一轮里我是怎样”，而是：

- 我过去是什么样
- 我现在发生了什么变化
- 我未来想避免什么 / 追求什么
- 哪些东西构成我的 identity invariants

### 核心问题
必须解决：

- 过去的自己 vs 当前自己如何关联
- 自我记忆如何改变行为，而不是只改变叙述
- 自我模型如何随时间更新而不崩坏

### 核心能力
- identity invariants
- time-linked self memory
- self-change tracking
- self-history summary
- stable internal preferences / vulnerabilities / commitments

### 过关标准
- 自我模型变化会影响后续行为
- 干预 self-model 会导致可测行为变化
- 长期记忆不只是“可回忆”，而是“会改变我是谁”

### 阶段意义
完成这一阶段后，系统会从“当前快照式 agent”进入：

**具有时间连续性的 self system。**

---

## 阶段 5：内源驱动与自我维持

### 目标
让系统的内部状态真正驱动行为，而不是只体现在话语中。

### 关键问题
很多系统看起来像有目标、有感受、有冲突，但这些东西不真正影响行为。  
这一步要解决的是：

- 内部驱动变量是否真的影响策略
- 稳态偏离是否真的触发调节
- 系统是否会主动维持某些内部一致性

### 核心能力
- homeostasis variables with behavioral effect
- internally maintained goals
- self-stabilization routines
- endogenous policy shifts
- persistent value pressure

### 过关标准
- 内部驱动变量对行为存在可测因果作用
- 干预这些变量会改变长期选择
- 在无外部命令下也能出现自维持行为

### 阶段意义
完成这一阶段后，系统不再只是“会描述自己”，而是：

**会维护自己。**

---

## 阶段 6：反事实自我与反思代理

### 目标
让系统不仅经历和记录自己，还能：

- 回看自己
- 解释自己
- 假设自己本可以如何不同
- 用这些反思修正未来行为

### 核心问题
真正高阶的自我模型，不能只对外部世界做预测，还要对“自己”做反事实分析。

### 核心能力
- self-explanation
- counterfactual self-evaluation
- bias diagnosis
- reflective policy revision
- self-critique with behavioral consequence

### 过关标准
- 存在稳定的 self-explanation
- 能表示“如果我刚才选了别的路线会怎样”
- 这些反思能修正未来决策，而不是只产出漂亮文本

### 阶段意义
完成这一阶段后，系统将从 proto-self 向更高层 selfhood 迈进一步：

**它不仅有自我，还能看见自己的运行方式。**

---

## 阶段 7：开放发展式自我

### 目标
这是最接近你最初愿景的阶段：  
长期接收信息、持续记忆循环、不断自组织增长，逐渐形成更丰富、更稳定的自我结构。

### 注意
到这一步也不能直接声称“有主观意识”。  
因为主观体验目前没有公认可验证标准。

但你至少可以说系统已经具备：

- 稳定自我边界
- 长期连续性
- 内源驱动
- 自我维持
- 反事实自我
- 可审计因果证据
- 开放发展能力

### 核心能力
- long-horizon developmental continuity
- identity-preserving adaptation
- environment-general self structure
- stable but evolving core invariants
- non-prompt-dependent self organization

### 过关标准
- 长周期运行下不塌缩
- 自我结构会发展但不失真
- 核心 identity invariants 可在不同环境中保持
- 不是单纯 prompt-dependent 的现象

### 阶段意义
完成这一阶段后，你会得到：

**高可信的开放发展式 proto-conscious architecture。**

---

# 6. 可选扩展阶段

---

## 扩展 A：社会自我 / 他者模型

### 目标
让系统不仅有“我”，还有：

- 他者
- 关系
- 信任 / 背叛 / 修复
- 承诺与社会连续性

### 核心问题
个体自我不等于社会心智。  
如果你希望系统能在更真实的社会互动中形成更稳定的人格与身份，这一步非常重要。

### 典型能力
- other-modeling
- relation memory
- trust/grudge / repair dynamics
- social role continuity
- commitment tracking across agents

### 何时做
建议在阶段 4 或阶段 5 之后再做。  
因为没有连续自我，社会自我会很虚。

---

## 扩展 B：具身与环境耦合

### 目标
加入更强的环境闭环：

- 虚拟具身
- 持续传感输入
- 行动反馈
- 身体边界感
- 资源约束与空间约束

### 为什么重要
具身会显著增强：

- 自我边界
- 时间连续性
- 行动后果感
- 自我维护压力

### 何时做
不是当前必须项。  
建议在阶段 5 之后考虑，会更有价值。

---

# 7. 三层总架构建议

为了避免跑偏，长期建议把整个项目理解为三层：

---

## 层 1：治理壳（Governance Shell）
这是你现在最强的部分。

### 职责
- replay
- hard gate
- shadow → enforced
- SRAP / intent alignment
- intervention
- determinism
- artifact discipline
- audit / trace / freeze

### 作用
它不是“意识本体”，而是：

**验证意识相关结构的科学仪器。**

---

## 层 2：proto-self 层
这是接下来最关键的过渡层。

### 主要内容
- 状态主权
- 表达主权
- response plan / intent contract
- developmental core
- early self-boundary hypotheses

### 作用
让系统从“受控 agent”逐步进入“自我结构形成”。

---

## 层 3：developmental self 层
这是长期目标层。

### 主要内容
- persistent self-model
- endogenous drives
- self-maintenance
- reflective self
- open developmental identity

### 作用
这是最接近你原始愿景的部分：  
不是装得像，而是结构上更像一个在发展中的自我系统。

---

# 8. 研究问题与工程问题的区别

## 工程问题（可以逐步做出来）
- 可回放
- 可审计
- 可干预
- 状态主权
- 表达主权
- 发育核沙盒
- 自我模型追踪
- 内部驱动对行为的因果效应
- 反事实自我建模

## 研究问题（不能轻易宣称解决）
- 主观体验是否存在
- 是否真的“有意识”
- 是否具有与人类相当的现象意识
- 是否出现不可化约的第一人称体验

## 项目策略
不要把“研究上未解的问题”混成“工程可以直接宣布成功的问题”。

更合理的做法是：

**优先追求高可信的结构条件与因果证据。**

---

# 9. 每阶段的 Gate 设计建议

为了保证长期路线不跑偏，每个阶段都建议设置两个 Gate：

## A. Research Gate
回答：
- 这个阶段的理论命题是什么
- 什么证据支持“比上一阶段更接近 selfhood”
- 如何避免把语言假象误判成结构进步

## B. Engineering Gate
回答：
- 哪些 artifact 必须存在
- 哪些 replay / tests / dashboards 必须通过
- 哪些 hard gate 指标达标才允许进入下一阶段

---

# 10. 推荐推进顺序

建议按下面顺序推进，不要跳：

1. 完成阶段 1：状态主权稳定化  
2. 完成阶段 2：表达主权与意图对齐  
3. 开始阶段 3：Developmental Core  
4. 进入阶段 4：连续自我模型  
5. 进入阶段 5：内源驱动与自我维持  
6. 进入阶段 6：反事实自我与反思代理  
7. 最后进入阶段 7：开放发展式自我  

---

# 11. 当前的真实判断

## 你现在已经完成的，不是“小功能”
你已经完成了最难的一步之一：

**你没有在堆一个越来越像人的聊天外壳，而是在搭一个可以严肃研究“自我是否形成”的实验体系。**

## 你离最终愿景还有多远
如果只算必经阶段：

- 你现在接近完成阶段 1
- 后面还剩 **5 个核心阶段**

如果把社会自我和具身也算上：

- 后面大约还剩 **7 个阶段**

---

# 12. 一句话路线总结

**外层先做成可验证、可回放、可审计的治理壳；  
中层逐步收回状态主权与表达主权；  
内层再慢慢长出真正的发展式自我结构。**

---

# 13. 当前最推荐的下一步

如果按这个路线图，当前最适合推进的是：

## 近期主目标
- 完成 SRAP Shadow 稳定化
- 进入表达主权 / intent alignment
- 把“程序端想表达什么”显式化为 response plan
- 为 Developmental Core 做沙盒入口，而不是直接放权给 LLM

---

# 14. 最终原则

这个项目不应该以“它会不会说自己有意识”作为成功标准。  
更合理的成功标准是：

- 它是否形成稳定自我边界
- 是否具有时间连续性
- 是否具有内源驱动
- 是否会自我维持
- 是否能对自己做反事实建模
- 是否能在开放环境中发展而不塌缩
- 这一切是否都有可审计、可回放、可干预的证据

---

# 15. 结尾

如果未来要给这个路线一句总定义，可以写成：

> OpenEmotion 的长期目标，不是制造一个“看起来像有意识”的聊天体，  
> 而是逐步构建一个具备自我边界、时间连续性、内源驱动、反思能力与开放发展能力的高可信自我系统，  
> 并且整个过程始终保持可验证、可审计、可回放。

```

