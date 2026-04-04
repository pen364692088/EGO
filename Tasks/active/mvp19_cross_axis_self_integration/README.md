# MVP19 Cross-Axis Self-Integration / Self-Maintenance Arbitration 执行包

```yaml
task_id: L3-20260404-MVP19-CSISA
created_at: "2026-04-04T00:00:00Z"
owner: "Codex"
layer: 3
type: dual_repo
repos: [EgoCore, OpenEmotion]
status: owner_package_completed
parent_authority: "Tasks/MVS_task_plan.md"
phase_authority: "Tasks/MVP19_task_plan.md"
predecessor: "WP13/MVP18"
same_subject_line: true
not_parallel_track: true
scope: "WP14 / MVP19 Cross-Axis Self-Integration / Self-Maintenance Arbitration"
claim_ceiling: "T10 only / formal_owner_package_completed"
```

---

## 真实目标

在不放开 authority 边界的前提下，把 `WP14/MVP19` 的 formal owner target 冻结到 `OpenEmotion/openemotion/selfhood_integration/*`，并把 `WP8~WP13` 的 frozen read surfaces、phase 1 `stability-first` arbitration policy、proposal-only outputs 与 upstream boundary freeze 全部收成可执行 authority package。

## 当前正式 owner target

- `OpenEmotion/openemotion/selfhood_integration/*`

## 当前正式主链 target

`frozen upstream read surfaces -> selfhood integration owner / bounded integration proposals -> proto_self_runtime / proto_self_adapter / proto_self_v2 -> governed downstream weighting and self_integration_writeback_candidate path`

## 当前锁定口径

- `MVP19` 是 `WP14`，接在 `WP13/MVP18` 后，不是新的主体线
- phase 1 只冻结 cross-axis integration semantics、formal intake/output 与 `stability-first` 仲裁策略
- `EgoCore` 继续保留 runtime / session / task / tool / transport、outward response contract、ask / wait / block / escalate、trace / replay / gate / audit / maintenance ledger、real-world execution / risk adjudication 的最终权威
- `WP8~WP13` 都保持 maintenance / frozen upstreams；`WP14` 只能读取冻结 surfaces，不能重写 upstream owner state
- `WP14` 当前不放开 live autonomy、OpenEmotion direct reply authority、broader transport claims、或任何 direct reply / tool / transport / authority escalation

## 当前范围

- authority / contract freeze
- formal selfhood integration owner package target
- bounded proto-self selfhood integration contract target
- EgoCore runtime selfhood integration bridge target
- `WP8~WP13` upstream boundary freeze
- legacy / compat / upstream read-only register
- subagent-ready task decomposition

## 当前状态

- 执行包状态：`owner_package_completed`
- authority freeze：`completed`
- `T00_AUTHORITY_FREEZE`：`completed`
- `T10` formal owner：`completed`
- `T20` proto_self_v2 contract：`pending`
- `T30` EgoCore runtime bridge：`pending`
- `T40` legacy demotion / compat map：`pending`
- `T50` causal validation：`pending`
- `T60` single controlled observation：`pending`
- `T70` batch controlled observation / aggregate：`pending`
- `T80` closeout / QA baseline：`pending`
- `T90` subagent assignment sync：`completed`
- 主链接线：`formal_owner_only_not_runtime_wired`
- 启用状态：`owner_infra_only`
- 当前 blocker：`none on the T10 owner-only axis`
- 当前最小动作：`T20_PROTO_SELF_CONTRACT_INTEGRATION`

## 当前已证实内容

- `Tasks/MVP19_task_plan.md` 已冻结 `WP14` 的 formal owner、authority source、IO contract、`WP8~WP13` boundary freeze 与 locked non-releases
- `contracts/SELFHOOD_INTEGRATION_CAPABILITY_OWNERSHIP.md` 已锁定 `WP14` 只拥有 cross-axis integration semantics，不拥有 upstream axis owner state
- `contracts/SELFHOOD_INTEGRATION_IO_CONTRACT.md` 已锁定：
  - formal intake 只来自 `WP8~WP13` 的 frozen read surfaces
  - phase 1 arbitration policy 是 `stability-first`
  - outputs 只允许 proposal-only / advisory / gated writeback candidates
- `SUBAGENT_ASSIGNMENT.md` 与 `cards/T00..T90` 已把初始 worker mapping、write scope 与后续实现顺序收成可执行 package

## T10 已证实内容

- `OpenEmotion/openemotion/selfhood_integration/*` 已成为 phase 1 的唯一 formal owner 落点
- owner state 已覆盖 `integration_state / cross_axis_priority_state / proposal_conflict_state / stabilize_explore_balance / repair_progress_balance / social_boundary_balance / integrated_tendency_proposal / axis_arbitration_hints / integration_ledger`
- owner store、revision log、replay、proposal-only governance 与 bounded runtime projection 已由 `OpenEmotion/tests/mvp19/test_selfhood_integration_owner_infra.py` 定向证明
- `axis_arbitration_hints` 当前仍保持 advisory-only，`integrated_tendency_proposal` 仍保持 `proposal_only + behavioral_authority = none + required_gate = self_integration_writeback_gate`
- `WP8~WP13` upstream owner surfaces 仍只作为 frozen read surfaces / read-only authority，不构成 `WP14` fallback owner 或 direct mutation authority

## 当前不做

- 不宣称 owner/runtime 已实现
- 不宣称当前 runtime mainline 已消费 `WP14`
- 不宣称 `E4/E5`
- 不宣称 observation started
- 不宣称 maintenance mode
- 不 reopen `WP8~WP13`
- 不放开 live autonomy
- 不放开 OpenEmotion direct reply authority
- 不放开 broader transport claims

## 执行入口

- authority：`Tasks/MVP19_task_plan.md`
- status：`STATUS.md`
- legacy register：`LEGACY_REFERENCE_REGISTER.md`
- contracts：`contracts/`
- task cards：`cards/`
- subagent assignment：`SUBAGENT_ASSIGNMENT.md`
