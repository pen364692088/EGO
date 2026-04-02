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
- [x] `memory_claim_gate` 已拿到 Telegram E4 真实样本
- [x] readiness report 已形成并区分 E4 / E2-E3
- [x] `WP1` readiness 复算已形成明确负向结论与缺口映射
- [x] 最小 host-side intent gate 的 `allowed_claims / forbidden_claims / grounding` 已形成正式 source
- [x] 最小 host-side intent gate 已拿到 Telegram E4 真实样本
- [x] Telegram 自然语言 control-plane 已完成一轮 direct_real 收口：默认 `seed_v0_2`、裸 `继续/继续说` 留在 `chat_mainline`、slash-only `/resume /replace /append /cancel` 的无冲突路径已拿到 E4

## 当前层级与主链状态

```yaml
current_layer: verification_blocked_by_clean_window
main_chain_status: partially_enabled
enabled_status: true
trigger_evidence:
  - host-chain slices have direct_real Telegram evidence
  - natural-language continue and slash-only control changes have direct_real Telegram evidence
  - WP0 docs are repo-tracked
  - fresh 7d/1d shadow reports exist, source separation is wired, and response_intent now appends checker_family-tagged shadow entries
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

1. 收集带新 `traffic_source / observation_source / checker_family` 字段的 post-separation 非对抗观察窗
2. 基于该干净窗口重跑 `numeric_leak` 与 SRAP Shadow readiness
3. `pending_task_conflict` 下 `/replace /append /cancel` 的成功路径当前已暂缓，不作为本轮 blocker；在获得干净观察窗前，不推进 `WP2`

## 对齐说明

- `WP7 / MVP12` 的第一批代码脚手架已经落在正式主链后面：
  - `runtime_v2 -> proto_self_runtime -> proto_self_adapter -> proto_self_v2`
  - `developmental_tick / developmental_replay`
  - `developmental_shadow` shadow-only writeback
- 2026-04-01 已补第一份 controlled evidence runner：
  - `OpenEmotion/tools/run_mvp12_controlled_evidence.py`
  - 当前已生成一份受控 E3 证据包：
    - `OpenEmotion/artifacts/mvp12/controlled_20260401_215912/*`
  - 结论：`governance_violation_count = 0`、`replay_consistent = true`
- 2026-04-01 同一 verifier 已补第一段 controlled `direct_real` 观察窗：
  - `OpenEmotion/artifacts/mvp12/controlled_20260401_220610/*`
  - 当前结果：`direct_real_cycles = 4`、`governance_violation_count = 0`、`observation_ref_count = 8`
  - 口径仍是 controlled observation，不等于 live 行为放权
- 2026-04-01 verifier 已进一步支持多窗口 `direct_real`：
  - `OpenEmotion/artifacts/mvp12/controlled_20260401_221524/*`
  - 当前结果：`direct_real_window_count = 3`、`direct_real_cycles = 12`、`governance_violation_count = 0`
  - 口径仍然是 controlled direct_real，不可冒充 `WP7 E4`
- 这不改变本执行包当前 scope 仍以 `WP0 / WP1` 为主。
- 当前口径必须保持：
  - `WP7` 还未正式启动
  - live 默认 `off`
  - 现有证据仅到受控 V2/V3，不得冒充 `WP7 E4`
