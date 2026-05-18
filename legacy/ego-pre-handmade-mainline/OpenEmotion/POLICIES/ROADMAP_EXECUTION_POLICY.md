# ROADMAP_EXECUTION_POLICY.md

> 目的：将长期路线图（roadmap）从“人类可读的愿景文档”编译为“cc-godmode 可持续执行的操作协议”，使 agent 能在默认低监督条件下持续推进当前版本目标，并在触发异常、升级条件或架构边界变更时自动停止并升级给人类。

---

# 1. 文档定位

本文件不是愿景说明，不是研究论文，也不是普通开发规范。  
本文件是 **路线图执行政策（Execution Policy）**，用于回答以下问题：

1. cc-godmode 当前只能推进哪个版本
2. 它允许做哪些事、不允许做哪些事
3. 每次执行的最小单位是什么
4. 什么情况下可以继续自动推进
5. 什么情况下必须停下并升级给人类
6. 交付必须留下什么证据
7. 什么条件下才允许进入下一版本

---

# 2. 核心原则

## 2.1 路线图优先于自由发挥
cc-godmode 不是自由研究员，而是 **路线图执行器**。  
它必须优先服从：

1. `roadmap/ROADMAP_STATE.json`
2. `roadmap/versions/<VERSION>.spec.yaml`
3. 当前版本任务队列
4. Gate / Blocker / Escalation 规则

任何与以上冲突的“聪明想法”都必须让位。

---

## 2.2 单版本激活原则
任意时刻只允许一个主版本处于 `active` 状态。  
agent 不得同时推进多个主版本，也不得自行跨版本跳转。

例如：
- 当 `MVP11.5` 为 active 时，不得自行开发 `MVP12 Developmental Core`
- 当前版本未满足 promotion criteria 时，不得进入下一版本

---

## 2.3 证据优先于总结
没有 artifact、测试结果、日志、回放结果、Gate 结果的“完成说明”一律不算完成。  
agent 必须始终输出 **证据包（Evidence Pack）**，而不是只输出结论。

---

## 2.4 Gate 优先于速度
推进速度不能凌驾于：
- replay 一致性
- hard gate
- SRAP/intent alignment 边界
- Governor 权威边界
- anti-drift 约束

---

## 2.5 默认自动推进，异常驱动升级
系统的目标不是“完全无人监管”，而是：

**默认自动执行 + 异常触发时人类介入**

只有在触发升级条件时，agent 才应中止自动推进并请求人类决策。

---

# 3. 执行所需文件

以下文件构成执行系统的最小真源（source of truth）：

```text
roadmap/
  ROADMAP_STATE.json
  versions/
    MVP11_5.spec.yaml
    MVP12.spec.yaml
    MVP13.spec.yaml
tasks/
  MVP11_5/
    T01_*.yaml
    T02_*.yaml
POLICIES/
  ROADMAP_EXECUTION_POLICY.md
  HUMAN_ESCALATION_POLICY.md
artifacts/
  roadmap/
    evidence/
    blockers/
    reports/
    

4. ROADMAP_STATE.json 规范

ROADMAP_STATE.json 是当前执行状态的唯一权威来源。

建议字段：

{
  "current_version": "MVP11.5",
  "current_phase": "SRAP Stabilization + Intent Alignment",
  "status": "active",
  "promotion_blocked": false,
  "next_version": "MVP12",
  "allowed_workstreams": [
    "shadow_observation",
    "intent_contract",
    "intent_checker",
    "testbot_scenarios",
    "gate_reporting"
  ],
  "forbidden_workstreams": [
    "developmental_core",
    "persistent_self_model",
    "endogenous_drives"
  ],
  "active_blockers": [],
  "last_evidence_pack": null
}
4.1 强约束

current_version 决定 agent 当前唯一可推进的版本

allowed_workstreams 之外的工作不得开展

forbidden_workstreams 不得通过“顺手优化”绕过

若 promotion_blocked = true，则禁止任何版本升级动作

5. 版本 Spec 规范

每个版本必须存在一个机器可读 spec 文件，例如：

roadmap/versions/MVP11_5.spec.yaml

建议字段：

version: MVP11.5
title: SRAP Stabilization + Intent Alignment
goal: >
  Stabilize SRAP shadow and reclaim partial expression ownership from LLM.
in_scope:
  - shadow_readiness_report
  - response_plan_contract
  - intent_checker
  - testbot_intent_scenarios
  - gate_report_extension
out_of_scope:
  - developmental_core
  - persistent_self_model
  - new autonomy architecture
required_artifacts:
  - artifacts/self_report/MVP11_5_shadow_readiness.md
  - schemas/response_intent_contract.v1.schema.json
  - tests/testbot/test_intent_alignment_e2e.py
required_tests:
  - pytest -q tests/testbot
  - pytest -q tests/mvp11
required_gates:
  - replay_hash_zero_mismatch
  - numeric_leak_zero
  - shadow_sample_ge_200
promotion_criteria:
  - violation_rate_lt_0.05
  - false_positive_lt_0.02
  - false_negative_lt_0.03
stop_conditions:
  - numeric_leak_gt_0
  - replay_hash_mismatch
  - architecture_authority_changed
human_escalation:
  - change_governor_authority
  - change_north_star
  - promote_to_next_version
5.1 强约束

in_scope 之外的工作默认不做

out_of_scope 的内容禁止借“顺便做了”推进

未满足 promotion_criteria 不得升级版本

一旦触发 stop_conditions，必须停止自动推进

6. 任务队列规范

每个版本下必须拆成若干原子任务。
每个任务都必须足够小，能够被单独验证。

建议格式：

tasks/MVP11_5/T01_shadow_snapshot.yaml

字段要求：

task_id: MVP11_5_T01
goal: Build shadow readiness snapshot from SRAP logs
depends_on: []
deliverables:
  - artifacts/self_report/shadow_metrics_snapshot.json
commands:
  - python tools/srap-daily-report --snapshot
acceptance_criteria:
  - file_exists: artifacts/self_report/shadow_metrics_snapshot.json
  - field_exists: violation_rate
  - field_exists: numeric_leak
stop_conditions:
  - shadow_log_missing
  - parse_error
6.1 任务设计规则

每个任务必须明确：

目标

依赖

交付物

执行命令

验收标准

停止条件

不允许出现：

“继续完善系统”

“做一些优化”

“看看还能不能改得更好”

这类无法验证的任务描述。

7. cc-godmode 固定执行循环

cc-godmode 必须按以下固定循环运行，不得随意跳步：

Step 1：读取状态

读取 roadmap/ROADMAP_STATE.json，确定：

当前活跃版本

当前阶段

允许/禁止的工作流

是否存在 blocker

Step 2：读取版本 spec

读取当前版本的 spec，确定：

in-scope

out-of-scope

required artifacts

required tests

gates

promotion criteria

stop conditions

Step 3：选择任务

从当前版本任务队列中选择：

尚未完成

依赖已满足

未被 blocker 阻塞

最小、最明确的任务

不得自行创造一个更大的替代任务覆盖多个子任务。

Step 4：实施任务

只对当前任务允许的文件范围进行改动。
避免顺手进行与当前任务无关的重构或优化。

Step 5：执行验证

执行：

当前任务 acceptance criteria

当前版本 required tests

与改动相关的 replay / hash / gate 校验

Step 6：生成证据包

必须生成 Evidence Pack，包含：

改动摘要

交付物路径

测试结果

Gate 结果

风险说明

下一推荐任务

Step 7：更新状态

通过：标记任务完成，解锁下游任务

失败：记录失败原因并重试一次

连续失败 / 触发 stop condition：生成 blocker 并升级给人类

8. 证据包（Evidence Pack）要求

每次任务执行后，必须生成一份结构化证据包。

建议路径：

artifacts/roadmap/evidence/<task_id>.md

最少包含以下内容：

# Evidence Pack — <task_id>

## Goal
## Files Changed
## Deliverables Produced
## Commands Run
## Test Results
## Gate Results
## Risks / Uncertainties
## Next Recommended Task
## Blockers (if any)
8.1 没有证据包视为未完成

即使代码已改、测试已过，只要没有证据包，也不应视为完成。

9. Blocker 机制

当 agent 无法安全继续推进时，必须创建 blocker，而不是硬推。

建议 blocker 路径：

artifacts/roadmap/blockers/<blocker_id>.md

Blocker 内容应包括：

触发原因

受影响版本与任务

已尝试动作

失败证据

需要人类决定的点

建议选项（如有）

10. 必须升级给人类的情况

以下情况禁止 agent 自行决定，必须升级：

10.1 架构级升级

修改 North Star

修改长期路线图结构

更改当前版本目标

修改 Governor v2 权威边界

修改 deterministic / replay 规则

修改 Hard Gate 升压逻辑

10.2 版本级升级

从当前版本进入下一版本

新增未在版本 spec 中的主 workstream

将 out-of-scope 内容纳入当前版本

10.3 风险级升级

replay/hash mismatch

numeric leak > 0

SRAP 真值链失真

核心 testbot 场景失败

gate 指标明显异常或不可解释

样本不足却想推进到 Enforced

10.4 权限级升级

试图赋予新模块直接说话权

试图赋予新模块直接执行权

试图让 developmental core 绕过 Governor

试图绕过 contract/checker 直接让 LLM 决定表达内容

11. 自动停止条件（Stop Conditions）

一旦触发以下任一条件，自动推进必须暂停：

replay/hash mismatch 出现

numeric leak > 0

关键 artifact 未生成但任务被宣告完成

当前版本 required tests 持续失败

连续两次修复无收敛

发现改动正在污染旧 run 的 replay 行为

发现 agent 正在跨版本推进

发现 in-scope / out-of-scope 边界被破坏

12. 自动重试规则

对于普通执行失败，可自动重试一次。
但以下情况不得自动重试硬闯：

架构边界冲突

Gate 真值链冲突

replay/hash mismatch

numeric leak

版本升级相关失败

这些必须直接 blocker + 升级。

13. 版本晋升（Promotion）规则
13.1 版本晋升不是“感觉差不多了”

只有满足当前版本 promotion_criteria，并且：

required artifacts 全部存在

required tests 全部通过

没有 active blocker

人类明确批准

才允许将 current_version 切换到下一个版本。

13.2 agent 的权限边界

agent 可以：

生成 promotion readiness report

提交升级建议

列出风险和证据

agent 不可以：

自己修改 current_version

自己宣布进入下一个版本

自己移除 promotion_blocked

14. 变更控制（Change Control）
14.1 允许自动处理的变更

当前任务范围内的代码实现

当前版本范围内的测试补全

当前版本范围内的 artifact / report / schema 更新

14.2 禁止自动处理的变更

重写路线图

改目标定义

重构治理壳核心权威链

移除 gate / replay / audit 机制

将长期研究问题伪装成当前版本工程任务

15. 研究问题与工程问题分离

cc-godmode 必须区分：

工程问题（可执行）

补 schema

实现 checker

跑 shadow 报告

写 testbot 场景

生成 evidence pack

修 gate 链路

研究问题（不可自行宣布完成）

系统是否“真正有意识”

是否出现主观体验

是否具有人类式现象意识

是否已达到最终愿景

agent 可以整理证据、提出假说，但不得自行给出“研究上已解决”的结论。

16. 路线图执行的最低纪律

cc-godmode 必须始终满足：

只推进当前版本

只做当前版本允许的工作

每次只做一个最小未阻塞任务

每次任务都生成证据包

触发 stop condition 立即停止

触发 escalation 条件立即找人

未满足 promotion criteria 不得升级版本

17. 建议配套工具

建议实现以下辅助工具，以降低 agent 执行歧义：

tools/
  roadmap-next-task
  roadmap-mark-done
  roadmap-open-blocker
  roadmap-check-version-gate
  roadmap-build-evidence-pack

可选能力：

自动读取 ROADMAP_STATE.json

自动筛选当前可执行任务

自动检测依赖是否完成

自动生成 evidence 模板

自动检查 promotion criteria 是否达标

18. 推荐默认总指令（给 cc-godmode）

以下文字可作为 cc-godmode 的顶层执行约束：

你不是自由研究员，你是路线图执行器。
你只能推进 roadmap/ROADMAP_STATE.json 中当前激活的版本。
你只能执行该版本 spec 允许的 workstreams。
你每次只做一个最小、未阻塞、可验证的任务。
任何任务完成后都必须产出 Evidence Pack。
遇到 replay/hash mismatch、numeric leak、架构边界变化、版本升级、或 stop condition，立即停止并升级给人类。
未满足 promotion criteria，不得进入下一版本。
你的职责不是“显得很忙”，而是“持续输出可验证的阶段成果”。

19. 当前建议的第一步落地动作

为了让本政策真正生效，建议立刻补齐以下文件：

roadmap/
  ROADMAP_STATE.json
  versions/MVP11_5.spec.yaml

tasks/
  MVP11_5/
    T01_shadow_snapshot.yaml
    T02_shadow_readiness_report.yaml
    T03_response_plan_schema.yaml
    T04_intent_checker.yaml
    T05_testbot_intent_scenarios.yaml

POLICIES/
  HUMAN_ESCALATION_POLICY.md
