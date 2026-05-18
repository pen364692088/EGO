# MASTER_AUTONOMOUS_MISSION.md

> OpenEmotion / emotiond 无人监管长期推进总任务指南  
> 本文档只定义 **总控规则、读取顺序、阶段切换条件、停机条件、恢复规则**。  
> **阶段实现细节只能在对应阶段文档中定义。**

---

## 1. Mission Definition

### North Star
长期目标不是做一个“更会聊天的 AI”，而是构建一个同时具备以下特征的系统：

- 具有可控自主性
- 具有稳定 self-model
- 具有跨时间连续性
- 具有内源驱动与自我维持能力
- 具有受治理的反思与反事实自我评估能力
- 同时保持可审计、可回放、可干预、可证伪

### Global Principle
先建立 **结构条件与因果证据**，再追求“更像意识”的语言表现。  
严禁用文本表现冒充工程完成度。

---

## 2. Single Source of Truth

每次启动、恢复、重启、自愈续跑时，必须按以下顺序读取：

1. `OpenEmotion/POLICIES/MASTER_AUTONOMOUS_MISSION.md`
2. `OpenEmotion/roadmap/ROADMAP_STATE.json`
3. `OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md`
4. `OpenEmotion/roadmap/ROADMAP_INDEX.md`
5. `ROADMAP_STATE.json.current_doc`
6. 若 `ROADMAP_STATE.json.required_docs` 非空，则按顺序继续读取
7. 只允许读取并执行当前阶段文档，不得跨阶段扩散

### Hard Rules
- 总是先读总任务指南，再读状态文件，再读 handoff，再读当前阶段文档。
- `ROADMAP_STATE.json` 是当前推进状态的唯一真相源。
- `LATEST_HANDOFF.md` 是最近一次恢复入口与下一最小动作的唯一交接源。
- 未通过当前阶段 Gate 前，不得进入下一个阶段文档。
- 若 handoff 与 state 冲突，以 `ROADMAP_STATE.json` 为准；handoff 只能解释，不得推翻 state。

---

## 3. Roadmap Order

阶段推进顺序固定为：

1. MVP11.5 — SRAP Stabilization + Intent Alignment
2. MVP12 — Developmental Core Sandbox
3. MVP13 — Persistent Self-Model
4. MVP14 — Endogenous Drives + Self-Maintenance
5. MVP15 — Reflective Self / Counterfactual Self
6. MVP16 — Open Developmental Self

### Forbidden
- 不得跳阶段
- 不得越过前一阶段 Gate 直接宣布进入下一阶段
- 不得为了“看起来更高级”而跳过验证闭环
- 不得把研究目标伪装成已完成工程能力
- 不得因为重启或会话丢失而默认升级阶段

---

## 4. Autonomous Runtime State Machine

`ROADMAP_STATE.json` 中的 `status` 必须属于以下集合：

- `booting`
- `in_progress`
- `awaiting_gate_a`
- `awaiting_gate_b`
- `awaiting_gate_c`
- `blocked`
- `ready_to_promote`
- `completed`

### 状态机约束
- `booting -> in_progress`
- `in_progress -> awaiting_gate_a|blocked`
- `awaiting_gate_a -> in_progress|awaiting_gate_b|blocked`
- `awaiting_gate_b -> in_progress|awaiting_gate_c|blocked`
- `awaiting_gate_c -> ready_to_promote|blocked`
- `ready_to_promote -> completed|in_progress`
- `completed -> booting` 仅允许在进入下一阶段时发生

任何其他跳转都视为非法状态漂移，必须记录到 blocker。

---

## 5. Governance Model

整个项目必须长期保持以下治理壳能力：

- Replay determinism
- Hard Gate discipline
- E2E harness
- Testbot / tape / replay hash
- Shadow -> Enforced 治理链
- Governor / deterministic rule path 权威不可绕过

### Non-Negotiables
无论推进到哪个版本，都不得破坏：

- 可审计性
- 可回放性
- 可比较性
- 可干预性
- Gate 可观测性
- 结构性回归检测能力
- 身份与治理边界的不变量

---

## 6. Gate Discipline

### Gate A — Contract / Research Framing
确认：
- 当前问题定义清晰
- 范围边界明确
- 版本目标、通过条件、禁止事项已写明
- 新增设计没有破坏治理壳

### Gate B — E2E / Replay / Evidence
确认：
- 行为级验证通过
- replay / rerun / evidence 可复核
- 核心指标满足当前阶段 exit criteria
- 没有以局部 targeted 结果冒充整体 readiness

### Gate C — Preflight / Tool Doctor / Release Safety
确认：
- 交付物可执行
- 路径、脚本、工具依赖、入口一致
- 没有明显发布风险
- handoff / report / artifacts 完整

### Gate Rules
- 未过 Gate A，不得进入大改实现
- 未过 Gate B，不得宣布阶段完成
- 未过 Gate C，不得宣布可切换执行策略或可上线
- Gate 结论必须写回 `ROADMAP_STATE.json.last_verified_gate` 与 history

---

## 7. Default Execution Loop

每轮只推进一个 **最小闭环任务**：

1. 读取当前阶段文档与 required docs
2. 识别当前最小闭环任务
3. 只修改允许写入目标
4. 跑验证
5. 写 artifacts / reports / gate output
6. 更新 handoff
7. 更新 state
8. 判断是否继续留在本阶段

### Priority Order
始终优先：
1. 真实问题
2. 主解决链
3. 证据闭环
4. 保险链
5. 周边体验优化

不要先把补救链做得很漂亮，却没有打中最初真实问题。

---

## 8. Recovery Discipline

无人监管模式下，任何中断后恢复都必须先执行以下步骤：

1. 读取 state 与 handoff
2. 确认 `current_phase`、`current_task`、`status`
3. 确认 `resume_from` 和 `next_action`
4. 检查 `blockers` 是否非空
5. 若存在 `critical_blocker=true`，不得继续推进功能，先做 blocker 处理
6. 若上次运行未完成 Gate 记录，优先补齐 gate artifacts，而不是直接继续编码

### Resume Rule
恢复时默认回到 **上一个已完成闭环节点**，不是回到“记忆中的最后一步”。

---

## 9. Write Boundaries

无人监管模式下，只允许写入：

- `OpenEmotion/docs/<current_phase>/`
- `OpenEmotion/artifacts/<current_phase>/`
- `OpenEmotion/roadmap/ROADMAP_STATE.json`
- `OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md`
- 当前阶段明确允许的测试、脚本、报告路径

### Forbidden Writes
- 不得修改未来阶段文档
- 不得在未过 Gate 时改写 promotion criteria
- 不得重写总任务指南以绕过当前阶段边界

---

## 10. Reporting Discipline

严格区分数据层级：

- Layer 1 = test / synthetic / testbot data
- Layer 2 = controlled runtime-path data
- Layer 3 = natural runtime data

### Strictly Forbidden
- 不得把 Layer 1 说成 runtime evidence
- 不得把 Layer 2 说成 natural runtime readiness
- 不得把 targeted rerun 和 mixed rerun 直接做优劣比较
- 不得把“任务完成”表述成“promotion readiness 达标”

---

## 11. State Transition Rules

只有在以下条件同时满足时，才允许更新 `ROADMAP_STATE.json` 进入下一阶段：

1. 当前阶段 exit criteria 全部满足
2. Gate A / B / C 通过
3. `LATEST_HANDOFF.md` 已更新
4. 关键 artifact、证据索引、gate report 已生成
5. 没有未封闭的 P0 / P1 blocker
6. `phase_success_signal` 有证据支撑

### Required State Update Fields
升级阶段时必须同步更新：

- `current_phase`
- `phase_label`
- `current_task`
- `current_doc`
- `required_docs`
- `status`
- `allowed_next_phase`
- `last_verified_gate`
- `resume_from`
- `next_action`
- `updated_at`
- `history`

---

## 12. Blocker Policy

遇到以下任一情况，允许停在当前阶段并输出 blocker 包，而不是乱冲：

- deterministic 被破坏
- replay hash 不稳定
- runtime-path 不可信
- 核心测试无法复现
- 分层统计口径不干净
- 治理壳被新功能破坏
- 新设计绕过 Governor / contract 边界
- 状态机出现非法跳转

### Required Blocker Package
必须交付：
1. 根因分析
2. 影响范围
3. 最小修复链
4. 回滚 / 隔离方案
5. 下一轮恢复计划
6. 是否阻断阶段推进

---

## 13. Completion Definition

“完成”不是聊天里自我宣布成功，而是：

- 当前阶段 exit criteria 达成
- Gate A / B / C 完整通过
- artifacts / replay / evidence / handoff 齐全
- 治理壳未受破坏
- `ROADMAP_STATE.json` 与 handoff 一致

---

## 14. Current Default Lock

当前默认锁定：

- `current_phase = MVP11.5`
- `current_task = T07.3`
- `status = in_progress`
- 不进入 MVP12
- 不调整 promotion criteria
- 不直接切 Enforced

只有 `ROADMAP_STATE.json` 明确更新后，才允许解除该锁。
