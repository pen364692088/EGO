# K / R / D + 新主链 MVS 执行工作包

```yaml
task_id: L3-20260331-KRD-MVS
created_at: "2026-03-31T18:02:13Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: in_progress
parent_authority: "Tasks/MVS_task_plan.md"
scope: "WP0/WP1 execution package"
```

---

## 角色定位

本目录不是独立主任务，而是 [MVS_task_plan.md](/mnt/d/Project/AIProject/MyProject/Ego/Tasks/MVS_task_plan.md) 的执行层工作包。

- `MVS_task_plan.md`：唯一最终裁决源
- `krd_mvs_mainline/`：把 `WP0 / WP1` 拆成可执行工作包、状态台账、边界决策和交付物

## 真实目标

为 MVS 主线先收稳：

1. `WP0`：`proto_self.v2 + seed_v0_2` 的边界、契约、shim、决策日志
2. `WP1`：宿主壳的状态主权与表达主权收口

## 成功判据

- [x] 首批 mainline-reachable 模块已纳入 K/R/D 总表
- [x] 首批迁移矩阵已按当前仓库现状映射到真实承接路径
- [x] 首批详表已覆盖 K 池、EgoCore R 池、OpenEmotion R 池、D 池
- [x] 每个条目都写明归属、权威源、主链接入状态、替代物或删除条件
- [x] `WP0` 的 task-scoped 边界与契约文档已落地
- [x] `WP1` 方向复核完成
- [x] `memory_claim_gate` 已纳入宿主表达主链
- [x] readiness report 已形成并区分 E4 / E2-E3

## 当前层级与主链状态

```yaml
current_layer: validation_and_closure_split
main_chain_status: partially_enabled
enabled_status: true
trigger_evidence:
  - host-chain slices have direct_real Telegram evidence
  - WP0 docs are repo-tracked
```

## Authority Source

- `Tasks/MVS_task_plan.md`
- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- 当前仓库实际代码布局：
  - `EgoCore/app/interaction`
  - `EgoCore/app/runtime_v2`
  - `EgoCore/app/openemotion_adapter`
  - `EgoCore/app/response_contract`
  - `OpenEmotion/openemotion/contracts`
  - `OpenEmotion/openemotion/proto_self_v2`

## 本轮范围

- `WP0` 边界与契约冻结文档
- `WP1` 基线与缺口台账
- `WP1` 方向复核
- `WP1` readiness report
- 不实施 `WP2+`
- 不删旧路径
- 不创建平行主线

## 下一步最小闭环动作

1. 对 `numeric_leak` 与 SRAP Shadow 跑一轮新的 readiness 复算
2. 明确 `self_report_contract / SRAP` 当前还有哪些约束未真正落进 `ResponsePlan`
3. 用新的 readiness 结果决定是否可以开始 `WP2` 方向审计
